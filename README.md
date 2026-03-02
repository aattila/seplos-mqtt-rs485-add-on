# Seplos MQTT RS485 Add-on

This project is forked from https://github.com/privatecoder/seplos-mqtt-rs485-add-on , please see the details there.

## What is changed

- Serial closes and reconects after each sessions to increase the communication fault tolerance.
- Adaptations for __Seplos V2 ZH__ series.

The Seplos BMS serial number and PCB number is:
![BMS Serial](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/bms_serial.png)

![BMS PCB](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/bms_pcb.png)

It is used and tested for the battery packs below:
![Battery Pack](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/battery_pack.png)

## RS485 -> USB

The following adapters are tested with success:

### Seplos BMS Adpter

![BMS PCB](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/adapter_seplos.png)

### Waveshare Adapter

![BMS PCB](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/adapter_ws.png)

### BMS Port Pinout

![BMS PCB](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/seplos_bms_pinout.png)

## Protocol

This BMS uses 19200 baud 8N1 port setup and it is wery important to __set the DIP switches__ for the right address. For this, please follow the binay logic, an example for three pack setup set the DIP switches are set in the following order Pack1: 10000000, Pack2: 01000000, Pack3: 11000000
