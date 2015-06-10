"""Serial script for interacting with the Inficon IC/5 Deposition Controller
9.Jun.2015 by David M Stewart"""

import serial, sys
from time import sleep
from random import gauss

def openIC5Serial(port,rate=9600):
    """openIC5Serial(port[,rate=9600]) -> serial object"""
    #IC/5 uses a user set bitrate and RTS/CTS.
    return serial.Serial(port,rate,rtscts=True,timeout=1)

def queryRate(ser,layer=1):
    """queryRate(serial object[,layer=1]) -> layer's rate (float)"""
    #SL 1 asks for the rate, but the layer must still be specified
    ser.write("SL 1 "+str(layer)+"\x06")
    #IC/5 returns "sxxx.xxx \x06" where s is " " or -
    #x is " " if 0, except 0.0
    return float(ser.read(8)[:-1].strip())

def queryThickness(ser,layer=1):
    """queryThickness(serial object[,layer=1]) -> layer's thickness (float)"""
    #SL 3 asks for the thickness, but the layer must be specified
    ser.write("SL 3 "+str(layer)+"\x06")
    #IC/5 returns "sxxxx.xxxx \x06", where s is " " or -
    return float(ser.read(10)[:-1].strip())

def queryTime(ser,layer=1):
    """queryTime(serial object[,layer=1]) -> deposition time in seconds (float)
Time is only between 00:00-99:59"""
    #SL 5 asks for the time since the begining of the specified layer
    ser.write("SL 5 "+str(layer)+"\x06")
    #IC/5 returns "xx:xx\x06"
    #User will need to address tracking the time when it wraps around.
    timeS = ser.read(7)[:-2]
    #needs to be finished
    #timeS needs to be converted to seconds.
    return (int(timeS[:2]),int(timeS[3:]))
	
def testRate():
    return round(gauss(2.3,0.2),2)

def concat(ent):
    #This needs to be better.
    #Ideally, the formatting would be something that can be easily read by Igor.
    return "\n".join(["\t".join([str(t),str(sr),str(rr),
                                 str(sl),str(rl)]) for (t,sr,rr,sl,rl) in ent])+\
                                 "\n***\n"
def rateform(raw):
    if raw < 0: return str(raw)
    else: return " "+str(raw)

#Establish parameters
logname = raw_input("Enter file name for log > ")
freq = float(raw_input("Time between entries? (s) > "))
#Might want to update this stuff to handle more user input.
#Of course, all that will go away with a GUI.
#uCoDep = raw_input("Codeposition (y/n) > ")


ser = openSerial(2)
print """Opening serial port
Monitoring time, layer 1 and 2 rate and thickness.
Logging data to ./"""+logname
print "Hit Ctrl+C to end..."
with open(logname, "w") as ffirst:
    ffirst.write("#IC/5 monitoring output\ntime(m,s)\tsubrate(A/s)\tsrcrate(A/s)\n")
with open(logname,'a') as fout:
    try:
        log, i, ilast = [], 0, 0
        while True:
            time = queryTime(ser)
            subrate = queryRate(ser,1)
            srcrate = queryRate(ser,2)
            subthick = queryThickness(ser,1)
            srcthick = queryThickness(ser,2)
            #print "\t".join([str(time),rateform(subrate),rateform(srcrate)])
            log.append((time,subrate,srcrate,subthick,srcthick))
            if (i-ilast) >= 600:
                fout.write(concat(log[ilast:]))
                ilast = i+1
            sleep(freq)
            i += 1
    except KeyboardInterrupt:
        fout.write(concat(log[ilast:]))

print "Closing serial port"
ser.close()
