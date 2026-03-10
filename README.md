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

![Seplos BMS Pinout](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/seplos-bms-pinout.png)

## Protocol

This BMS uses 19200 baud 8N1 port setup and it is wery important to __set the DIP switches__ for the right address. For this, please follow the binay logic, an example for three pack setup set the DIP switches are set in the following order Pack1: 10000000, Pack2: 01000000, Pack3: 11000000

## Dashboard

You can add your mqtt entities to the Home Assistant dashboard by using a custom card from HACS named: bms-battery-cells-card.
A three pack battery setup looks like this:

![Dashboard](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/dashboard.png)

## For more robustness

In case ig you are using multiple USB serial devices you will facing with the following problems:

- Not enough power on the PC's USB hub or it is limited, so your USB adapter will randomly kicked off.
- After a restart or after a HA OS update (that is restart too) the mapped USB serial port such /dev/ttyUSB0 will rearranged and your adapters will get another ports that is configured in the HA add-on.

So, in this situation or if you want to introduce more robustness in your setup you need to change your adapters with something more industrial such Serial to Ethernet adatpters.

This [waveshare serial to eth adapter](https://www.waveshare.com/wiki/RS232/485/422_TO_POE_ETH_(B)#Software) is tested with succes.

![Solar Inverter 11k](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/ws-eth.jpg)
![Solar Inverter 11k](https://raw.githubusercontent.com/aattila/seplos-mqtt-rs485-add-on/main/img/ws-poe.jpg)

To configure this adapters:

- First setup the adapter. The default access is 192.168.1.200 with no password, set the DHCP in case if you want and set the baud rate. There is NO need to set the Modbus TCP to RTU protocoll, so leave that field untouched or set None!
- In HA at the add-on configuration panel set the adapter IP address and port and specify a local serial port (/tmp/vcom0 an example) where the TCP stream will be mapped (and vice-versa)
- Pay attention for the serial port when you are using multiple devices such this, so those needs to be different for each device eg. /tmp/vcom0, /tmp/vcom1, ...

