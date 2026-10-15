/*
   Programador ICP SinoWealth para Arduino Uno / Nano (ATmega328P).
   Porte do firmware do sinodude (https://github.com/carlossless/sinodude), GPL-3.0.
*/

#include <Arduino.h>

// Pinos ICP no Arduino Nano
#define PIN_TDO   2 // D2 (Input from SinoWealth TDO)
#define PIN_TMS   3 // D3 (Output to SinoWealth TMS)
#define PIN_TDI   4 // D4 (Output to SinoWealth TDI)
#define PIN_TCK   5 // D5 (Output to SinoWealth TCK)
#define PIN_PWR   6 // D6 (alimentacao do chip, HIGH = ligado)

#define VERSION_MAJOR 3
#define VERSION_MINOR 0

// Acesso direto as portas do ATmega328P
#define TCK_HIGH() (PORTD |= (1 << PD5))
#define TCK_LOW()  (PORTD &= ~(1 << PD5))
#define TDI_HIGH() (PORTD |= (1 << PD4))
#define TDI_LOW()  (PORTD &= ~(1 << PD4))
#define TMS_HIGH() (PORTD |= (1 << PD3))
#define TMS_LOW()  (PORTD &= ~(1 << PD3))
#define TDO_READ() ((PIND & (1 << PD2)) != 0)

namespace cmd {
    const uint8_t CMD_PING = 0x01;
    const uint8_t CMD_GET_VERSION = 0x02;
    const uint8_t CMD_CONNECT = 0x03;
    const uint8_t CMD_DISCONNECT = 0x04;
    const uint8_t CMD_GET_ID = 0x05;
    const uint8_t CMD_SET_CONFIG = 0x06;
    const uint8_t CMD_GET_CONFIG = 0x07;
    const uint8_t CMD_READ_FLASH = 0x08;
    const uint8_t CMD_WRITE_FLASH = 0x09;
    const uint8_t CMD_ERASE_FLASH_SECTOR = 0x0A;
    const uint8_t CMD_MASS_ERASE = 0x0B;
    const uint8_t CMD_READ_CUSTOM_REGION = 0x0C;
    const uint8_t CMD_WRITE_CUSTOM_REGION = 0x0D;
    const uint8_t CMD_ERASE_EEPROM_PAGE = 0x0E;
    const uint8_t CMD_SEND_KEY = 0x0F;

    const uint8_t RSP_OK = 0x00;
    const uint8_t RSP_ERR = 0xFF;
    const uint8_t RSP_DATA = 0x01;
}

namespace icp_cmd {
    const uint8_t ICP_SET_IB_OFFSET_L = 0x40;
    const uint8_t ICP_SET_IB_OFFSET_H = 0x41;
    const uint8_t ICP_SET_IB_DATA = 0x42;
    const uint8_t ICP_GET_IB_OFFSET = 0x43;
    const uint8_t ICP_READ_FLASH = 0x44;
    const uint8_t ICP_PING = 0x49;
    const uint8_t ICP_READ_CUSTOM_BLOCK = 0x4A;
    const uint8_t ICP_SET_XPAGE = 0x4C;
}

enum Mode {
    MODE_UNSET,
    MODE_READY,
    MODE_ICP,
    MODE_JTAG
};

Mode current_mode = MODE_UNSET;
int chip_type = -1;
uint8_t buffer[1024];

void send_icp_byte(uint8_t byte);
uint8_t receive_icp_byte();
void reset_controller();
void start_mode(Mode m);
void switch_mode(Mode m);
bool check_connection();

void setup_pins() {
    pinMode(PIN_TDO, INPUT_PULLUP);
    pinMode(PIN_TMS, OUTPUT);
    pinMode(PIN_TDI, OUTPUT);
    pinMode(PIN_TCK, OUTPUT);
    pinMode(PIN_PWR, OUTPUT);

    digitalWrite(PIN_PWR, LOW);
    TCK_LOW();
    TDI_LOW();
    TMS_LOW();
}

void power_on() {
    digitalWrite(PIN_PWR, HIGH);
}

void power_off() {
    digitalWrite(PIN_PWR, LOW);
    current_mode = MODE_UNSET;
}

void ping_icp() {
    if (current_mode != MODE_ICP) return;
    send_icp_byte(icp_cmd::ICP_PING);
    send_icp_byte(0xFF);
}

void send_icp_byte(uint8_t byte) {
    for (int i = 0; i < 8; i++) {
        if (byte & 0x80) TDI_HIGH();
        else TDI_LOW();

        delayMicroseconds(2);
        TCK_HIGH();
        delayMicroseconds(2);
        TCK_LOW();
        byte <<= 1;
    }
    delayMicroseconds(2);
    TCK_HIGH();
    delayMicroseconds(2);
    TCK_LOW();
    TDI_LOW();
}

uint8_t receive_icp_byte() {
    uint8_t byte = 0;
    uint8_t mask = 1;
    for (int i = 0; i < 8; i++) {
        delayMicroseconds(2);
        TCK_HIGH();
        delayMicroseconds(2);
        TCK_LOW();
        if (TDO_READ()) {
            byte |= mask;
        }
        mask <<= 1;
    }
    delayMicroseconds(2);
    TCK_HIGH();
    delayMicroseconds(2);
    TCK_LOW();
    return byte;
}

void jtag_next_state(bool tms) {
    if (tms) TMS_HIGH();
    else TMS_LOW();
    delayMicroseconds(2);
    TCK_HIGH();
    delayMicroseconds(2);
    TCK_LOW();
}

bool jtag_next_state_read(bool tms) {
    if (tms) TMS_HIGH();
    else TMS_LOW();
    delayMicroseconds(2);
    TCK_HIGH();
    delayMicroseconds(2);
    bool bit = TDO_READ();
    TCK_LOW();
    return bit;
}

void jtag_next_state_out(bool tms, bool tdi) {
    if (tms) TMS_HIGH();
    else TMS_LOW();
    if (tdi) TDI_HIGH();
    else TDI_LOW();
    delayMicroseconds(2);
    TCK_HIGH();
    delayMicroseconds(2);
    TCK_LOW();
}

void jtag_send_instruction(uint8_t instruction) {
    jtag_next_state(false); // Idle
    jtag_next_state(true);  // Select-DR
    jtag_next_state(true);  // Select-IR
    jtag_next_state(false); // Capture-IR
    jtag_next_state(false); // Shift-IR
    for (int i = 0; i < 4; i++) {
        bool last = (i == 3);
        bool bit = (instruction >> i) & 1;
        jtag_next_state_out(last, bit);
    }
    TDI_LOW();
    jtag_next_state(true);  // Update-IR
    jtag_next_state(false); // Idle
}

uint16_t jtag_receive_16(uint8_t bit_len) {
    jtag_next_state(true);  // Select-DR
    jtag_next_state(false); // Capture-DR
    jtag_next_state(false); // Shift-DR

    uint16_t val = 0;
    for (int i = 0; i < bit_len; i++) {
        bool last = (i == bit_len - 1);
        bool bit = jtag_next_state_read(last);
        if (bit) val |= ((uint16_t)1 << (bit_len - 1 - i));
    }
    jtag_next_state(true);  // Update-DR
    jtag_next_state(false); // Idle
    return val;
}

void jtag_send_bits(uint8_t bit_len, uint32_t val) {
    for (int i = 0; i < bit_len; i++) {
        bool bit = (val >> i) & 1;
        bool last = (i == bit_len - 1);
        jtag_next_state_out(last, bit);
    }
    TDI_LOW();
}

void reset_controller() {
    if (current_mode == MODE_ICP || current_mode == MODE_READY) {
        TCK_HIGH();
        delayMicroseconds(8);
        TMS_HIGH();
        delayMicroseconds(2);
        TMS_LOW();
        delayMicroseconds(2);
    } else if (current_mode == MODE_JTAG) {
        for (int i = 0; i < 35; i++) {
            jtag_next_state(true);
        }
        TCK_HIGH();
        TMS_LOW();
    }
    current_mode = MODE_READY;
}

void start_mode(Mode m) {
    TCK_LOW();
    delayMicroseconds(2);
    uint8_t mode_val = 0;
    if (m == MODE_READY) mode_val = 1;
    else if (m == MODE_ICP) mode_val = 150;
    else if (m == MODE_JTAG) mode_val = 165;

    for (int i = 0; i < 8; i++) {
        if (mode_val & 0x80) TDI_HIGH();
        else TDI_LOW();

        TCK_HIGH();
        delayMicroseconds(2);
        TCK_LOW();
        delayMicroseconds(2);
        mode_val <<= 1;
    }

    TCK_HIGH(); delayMicroseconds(2); TCK_LOW(); delayMicroseconds(2);
    TCK_HIGH(); delayMicroseconds(2); TCK_LOW(); delayMicroseconds(2);
}

void switch_mode(Mode m) {
    if (current_mode == m) return;
    if (current_mode != MODE_READY) {
        reset_controller();
    }
    current_mode = m;
    start_mode(m);

    if (current_mode == MODE_ICP) {
        delayMicroseconds(800);
        ping_icp();
    } else if (current_mode == MODE_JTAG) {
        for (int i = 0; i < 8; i++) jtag_next_state(true);
        jtag_send_instruction(2);
        jtag_send_bits(4, 4);
        jtag_send_instruction(3);
        jtag_send_bits(23, 0x403000UL);
        delayMicroseconds(50);
        jtag_send_bits(23, 0x402000UL);
        jtag_send_bits(23, 0x400000UL);
        jtag_send_instruction(2);
        jtag_send_bits(4, 1);
        jtag_send_instruction(12);
    }
}

bool check_connection() {
    switch_mode(MODE_ICP);
    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_L);
    send_icp_byte(0x69);
    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_H);
    send_icp_byte(0xFF);

    send_icp_byte(icp_cmd::ICP_GET_IB_OFFSET);
    uint8_t resp = receive_icp_byte();
    receive_icp_byte();

    return (resp == 0x69);
}

bool connect_target() {
    power_off();
    delay(50);
    power_on();
    delay(5);

    TMS_HIGH();
    TDI_HIGH();
    TCK_HIGH();
    delay(3);

    TCK_LOW();
    delayMicroseconds(2);
    TCK_HIGH();
    delayMicroseconds(50);

    for (int i = 0; i < 165; i++) {
        TMS_LOW(); delayMicroseconds(2);
        TMS_HIGH(); delayMicroseconds(2);
    }

    for (int i = 0; i < 105; i++) {
        TDI_LOW(); delayMicroseconds(2);
        TDI_HIGH(); delayMicroseconds(2);
    }

    for (int i = 0; i < 90; i++) {
        TCK_LOW(); delayMicroseconds(2);
        TCK_HIGH(); delayMicroseconds(2);
    }

    for (uint16_t i = 0; i < 20480; i++) {
        TMS_LOW(); delayMicroseconds(2);
        TMS_HIGH(); delayMicroseconds(2);
    }

    delayMicroseconds(8);
    TMS_LOW();

    current_mode = MODE_ICP;
    start_mode(MODE_ICP);

    for (uint16_t i = 0; i < 1644; i++) {
        TCK_HIGH(); delayMicroseconds(2);
        TCK_LOW(); delayMicroseconds(2);
    }

    reset_controller();
    delayMicroseconds(10);

    return check_connection();
}

uint16_t jtag_get_id() {
    switch_mode(MODE_JTAG);
    jtag_send_instruction(14); // JTAG_IDCODE
    return jtag_receive_16(16);
}

void icp_select_program_space(uint8_t c_type) {
    uint8_t space = 0xF0;
    if (c_type == 0) space = 0xFE;
    send_icp_byte(0x46);
    send_icp_byte(space);
    send_icp_byte(0xFF);
}

void icp_select_erase_space() {
    send_icp_byte(0x46);
    send_icp_byte(0xF0);
    send_icp_byte(0xFF);
}

uint8_t icp_erase_opcode(uint8_t mode, uint8_t sub_flag, uint8_t c_type) {
    if (mode == 0) {
        return (sub_flag == 0) ? 0xE6 : 0x55;
    } else if (mode == 1) {
        return (c_type == 7) ? 0x4B : 0xAA;
    } else if (mode == 2) {
        return (c_type == 7) ? 0x3C : 0xDA;
    } else if (mode == 3) {
        return 0x5E;
    } else if (mode == 4) {
        return 0x2D;
    }
    return 0xC3;
}

bool icp_read_flash(uint32_t addr, uint8_t* buf, uint16_t len, bool custom_block) {
    switch_mode(MODE_ICP);
    if (chip_type < 0) return false;

    if (chip_type != 1) {
        send_icp_byte(0x46);
        send_icp_byte(0xFE);
        send_icp_byte(0xFF);
    }

    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_L);
    send_icp_byte((uint8_t)(addr & 0xFF));
    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_H);
    send_icp_byte((uint8_t)((addr >> 8) & 0xFF));

    if (chip_type == 4 || chip_type == 7) {
        send_icp_byte(icp_cmd::ICP_SET_XPAGE);
        send_icp_byte((uint8_t)((addr >> 16) & 0xFF));
    }

    send_icp_byte(custom_block ? icp_cmd::ICP_READ_CUSTOM_BLOCK : icp_cmd::ICP_READ_FLASH);

    for (uint16_t i = 0; i < len; i++) {
        buf[i] = receive_icp_byte();
    }

    reset_controller();
    return true;
}

bool icp_write_region(uint32_t addr, const uint8_t* data, uint16_t len, bool custom_block) {
    switch_mode(MODE_ICP);
    if (chip_type < 0 || len < 2) return false;

    icp_select_program_space(chip_type);

    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_L);
    send_icp_byte((uint8_t)(addr & 0xFF));
    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_H);
    send_icp_byte((uint8_t)((addr >> 8) & 0xFF));

    if (chip_type == 4 || chip_type == 7) {
        send_icp_byte(icp_cmd::ICP_SET_XPAGE);
        send_icp_byte((uint8_t)((addr >> 16) & 0xFF));
    }

    send_icp_byte(icp_cmd::ICP_SET_IB_DATA);
    send_icp_byte(data[0]);

    uint8_t cmd = custom_block ? 0xA5 : 0x6E;
    send_icp_byte(cmd);
    send_icp_byte(0x15);
    send_icp_byte(0x0A);
    send_icp_byte(0x09);
    send_icp_byte(0x06);
    send_icp_byte(data[1]);

    delayMicroseconds(10);
    send_icp_byte(0x00);
    if (!TDO_READ()) return false;

    for (uint16_t i = 2; i < len; i++) {
        send_icp_byte(data[i]);
        delayMicroseconds(5);
        send_icp_byte(0x00);
        if (!TDO_READ()) return false;
    }

    send_icp_byte(0x00);
    send_icp_byte(0xAA);
    if (!TDO_READ()) return false;

    send_icp_byte(0x00);
    send_icp_byte(0x00);
    delayMicroseconds(5);

    reset_controller();
    return true;
}

bool icp_mass_erase(uint8_t mode) {
    switch_mode(MODE_ICP);
    if (chip_type < 0) return false;

    icp_select_erase_space();

    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_L);
    send_icp_byte(0x00);
    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_H);
    send_icp_byte(0x00);

    if (chip_type == 4 || chip_type == 7) {
        send_icp_byte(icp_cmd::ICP_SET_XPAGE);
        send_icp_byte(0x00);
    }

    send_icp_byte(icp_cmd::ICP_SET_IB_DATA);
    send_icp_byte(0x00);

    uint8_t erase_cmd = icp_erase_opcode(mode, 0, chip_type);
    send_icp_byte(erase_cmd);
    send_icp_byte(0x15);
    send_icp_byte(0x0A);
    send_icp_byte(0x09);
    send_icp_byte(0x06);
    send_icp_byte(0xFF);

    TDI_HIGH();
    delay(30);

    uint16_t waited = 0;
    while (!TDO_READ()) {
        delay(5);
        send_icp_byte(0x00);
        waited += 5;
        if (waited >= 5000) {
            reset_controller();
            return false;
        }
    }

    reset_controller();
    return true;
}

bool icp_erase_at(uint32_t addr, uint8_t sub_flag) {
    switch_mode(MODE_ICP);
    if (chip_type < 0) return false;

    icp_select_erase_space();

    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_L);
    send_icp_byte((uint8_t)(addr & 0xFF));
    send_icp_byte(icp_cmd::ICP_SET_IB_OFFSET_H);
    send_icp_byte((uint8_t)((addr >> 8) & 0xFF));

    if (chip_type == 4 || chip_type == 7) {
        send_icp_byte(icp_cmd::ICP_SET_XPAGE);
        send_icp_byte((uint8_t)((addr >> 16) & 0xFF));
    }

    send_icp_byte(icp_cmd::ICP_SET_IB_DATA);
    send_icp_byte(0x00);

    send_icp_byte(icp_erase_opcode(0, sub_flag, chip_type));
    send_icp_byte(0x15);
    send_icp_byte(0x0A);
    send_icp_byte(0x09);
    send_icp_byte(0x06);
    send_icp_byte(0x00);

    delay(300);
    send_icp_byte(0x00);
    bool status = TDO_READ();
    send_icp_byte(0x00);

    reset_controller();
    return status;
}

uint8_t read_blocking() {
    while (!Serial.available());
    return Serial.read();
}

void setup() {
    setup_pins();
    Serial.begin(115200);
}

void loop() {
    if (!Serial.available()) return;
    uint8_t c = Serial.read();

    switch (c) {
        case cmd::CMD_PING:
            Serial.write(cmd::RSP_OK);
            Serial.write('S');
            Serial.write('W');
            break;

        case cmd::CMD_GET_VERSION:
            Serial.write(cmd::RSP_DATA);
            Serial.write(VERSION_MAJOR);
            Serial.write(VERSION_MINOR);
            break;

        case 0x55: {
            bool ok = connect_target();
            uint16_t jid = jtag_get_id();
            Serial.write(cmd::RSP_DATA);
            Serial.write(ok ? 1 : 0);
            Serial.write((uint8_t)(jid & 0xFF));
            Serial.write((uint8_t)(jid >> 8));
            break;
        }

        case cmd::CMD_CONNECT:
            if (connect_target()) {
                Serial.write(cmd::RSP_OK);
            } else {
                Serial.write(cmd::RSP_ERR);
            }
            break;

        case cmd::CMD_DISCONNECT:
            power_off();
            Serial.write(cmd::RSP_OK);
            break;

        case cmd::CMD_GET_ID: {
            uint16_t id = jtag_get_id();
            Serial.write(cmd::RSP_DATA);
            Serial.write((uint8_t)(id & 0xFF));
            Serial.write((uint8_t)(id >> 8));
            break;
        }

        case cmd::CMD_SET_CONFIG:
            chip_type = read_blocking();
            Serial.write(cmd::RSP_OK);
            break;

        case cmd::CMD_GET_CONFIG:
            if (chip_type >= 0) {
                Serial.write(cmd::RSP_DATA);
                Serial.write((uint8_t)chip_type);
            } else {
                Serial.write(cmd::RSP_ERR);
            }
            break;

        case cmd::CMD_READ_FLASH: {
            uint32_t addr = 0;
            addr |= (uint32_t)read_blocking();
            addr |= ((uint32_t)read_blocking()) << 8;
            addr |= ((uint32_t)read_blocking()) << 16;
            addr |= ((uint32_t)read_blocking()) << 24;

            uint16_t len = 0;
            len |= (uint16_t)read_blocking();
            len |= ((uint16_t)read_blocking()) << 8;
            if (len > sizeof(buffer)) len = sizeof(buffer);

            if (icp_read_flash(addr, buffer, len, false)) {
                Serial.write(cmd::RSP_DATA);
                Serial.write((uint8_t)(len & 0xFF));
                Serial.write((uint8_t)(len >> 8));
                Serial.write(buffer, len);
            } else {
                Serial.write(cmd::RSP_ERR);
            }
            break;
        }

        case cmd::CMD_READ_CUSTOM_REGION: {
            uint32_t addr = 0;
            addr |= (uint32_t)read_blocking();
            addr |= ((uint32_t)read_blocking()) << 8;
            addr |= ((uint32_t)read_blocking()) << 16;
            addr |= ((uint32_t)read_blocking()) << 24;

            uint16_t len = 0;
            len |= (uint16_t)read_blocking();
            len |= ((uint16_t)read_blocking()) << 8;
            if (len > sizeof(buffer)) len = sizeof(buffer);

            if (icp_read_flash(addr, buffer, len, true)) {
                Serial.write(cmd::RSP_DATA);
                Serial.write((uint8_t)(len & 0xFF));
                Serial.write((uint8_t)(len >> 8));
                Serial.write(buffer, len);
            } else {
                Serial.write(cmd::RSP_ERR);
            }
            break;
        }

        case cmd::CMD_WRITE_FLASH: {
            uint32_t addr = 0;
            addr |= (uint32_t)read_blocking();
            addr |= ((uint32_t)read_blocking()) << 8;
            addr |= ((uint32_t)read_blocking()) << 16;
            addr |= ((uint32_t)read_blocking()) << 24;

            uint16_t len = 0;
            len |= (uint16_t)read_blocking();
            len |= ((uint16_t)read_blocking()) << 8;
            if (len > sizeof(buffer)) len = sizeof(buffer);

            for (uint16_t i = 0; i < len; i++) {
                buffer[i] = read_blocking();
            }

            if (icp_write_region(addr, buffer, len, false)) {
                Serial.write(cmd::RSP_OK);
            } else {
                Serial.write(cmd::RSP_ERR);
            }
            break;
        }

        case cmd::CMD_WRITE_CUSTOM_REGION: {
            uint32_t addr = 0;
            addr |= (uint32_t)read_blocking();
            addr |= ((uint32_t)read_blocking()) << 8;
            addr |= ((uint32_t)read_blocking()) << 16;
            addr |= ((uint32_t)read_blocking()) << 24;

            uint16_t len = 0;
            len |= (uint16_t)read_blocking();
            len |= ((uint16_t)read_blocking()) << 8;
            if (len > sizeof(buffer)) len = sizeof(buffer);

            for (uint16_t i = 0; i < len; i++) {
                buffer[i] = read_blocking();
            }

            if (icp_write_region(addr, buffer, len, true)) {
                Serial.write(cmd::RSP_OK);
            } else {
                Serial.write(cmd::RSP_ERR);
            }
            break;
        }

        case cmd::CMD_MASS_ERASE: {
            uint8_t mode = read_blocking();
            if (icp_mass_erase(mode)) {
                Serial.write(cmd::RSP_OK);
            } else {
                Serial.write(cmd::RSP_ERR);
            }
            break;
        }

        case cmd::CMD_ERASE_FLASH_SECTOR: {
            uint32_t addr = 0;
            addr |= (uint32_t)read_blocking();
            addr |= ((uint32_t)read_blocking()) << 8;
            addr |= ((uint32_t)read_blocking()) << 16;
            addr |= ((uint32_t)read_blocking()) << 24;

            if (icp_erase_at(addr, 0)) {
                Serial.write(cmd::RSP_OK);
            } else {
                Serial.write(cmd::RSP_ERR);
            }
            break;
        }

        case cmd::CMD_ERASE_EEPROM_PAGE: {
            uint32_t addr = 0;
            addr |= (uint32_t)read_blocking();
            addr |= ((uint32_t)read_blocking()) << 8;
            addr |= ((uint32_t)read_blocking()) << 16;
            addr |= ((uint32_t)read_blocking()) << 24;

            if (icp_erase_at(addr, 1)) {
                Serial.write(cmd::RSP_OK);
            } else {
                Serial.write(cmd::RSP_ERR);
            }
            break;
        }

        case cmd::CMD_SEND_KEY: {
            uint8_t key[8];
            for (int i = 0; i < 8; i++) key[i] = read_blocking();
            uint32_t v_addr = 0;
            v_addr |= (uint32_t)read_blocking();
            v_addr |= ((uint32_t)read_blocking()) << 8;
            v_addr |= ((uint32_t)read_blocking()) << 16;
            v_addr |= ((uint32_t)read_blocking()) << 24;

            switch_mode(MODE_ICP);
            send_icp_byte(0x4B);
            for (int i = 0; i < 8; i++) send_icp_byte(key[i]);

            uint8_t marker = 0;
            icp_read_flash(v_addr, &marker, 1, true);
            Serial.write(cmd::RSP_DATA);
            Serial.write(marker);
            break;
        }

        default:
            Serial.write(cmd::RSP_ERR);
            break;
    }
}
