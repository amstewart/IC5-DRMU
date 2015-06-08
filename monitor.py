"""Serial script for interacting with the Inficon IC/5 Deposition Controller
5.Jun.2015 by David M Stewart"""

import serial
from time import sleep

def openSerial(port,rate=9600):
    return serial.Serial(port,rate,rtscts=True,timeout=1)

def queryRate(ser,layer=1):
    ser.write("SL 1 "+str(layer)+"\x06")
    return float(ser.read(8)[:-1].strip())

def queryThickness(ser,layer=1):
    ser.write("SL 3 "+str(layer)+"\x06")
    return float(ser.read(10)[:-1].strip())

def queryTime(ser,layer=1):
    ser.write("SL 5 "+str(layer)+"\x06")
    timeS = ser.read(7)[:-2]
    return (int(timeS[:2]),int(timeS[3:]))

ser = openSerial(2)
print "Opening serial port", 3
print "Closing serial port"
ser.close()
