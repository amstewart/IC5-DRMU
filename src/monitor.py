"""Serial script for interacting with the Inficon IC/5 Deposition Controller"""

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
    #x is " " if 0, but at least 0.0
    return float(ser.read(8)[:-1].strip())

def queryThickness(ser,layer=1):
    """queryThickness(serial object[,layer=1]) -> layer's thickness (float)"""
    #SL 3 asks for the thickness, but the layer must be specified
    ser.write("SL 3 "+str(layer)+"\x06")
    #IC/5 returns "sxxx.xxx \x06", where s is " " or -
    return float(ser.read(10)[:-1].strip())

def queryTime(ser,layer=1):
    """queryTime(serial object[,layer=1]) -> deposition time in seconds (int)
    Time is only 0-5999"""
    #SL 5 asks for the time since the begining of the specified layer
    ser.write("SL 5 "+str(layer)+"\x06")
    #IC/5 returns "xx:xx \x06"
    #User will need to address tracking the time when it wraps around.
    timeS = ser.read(7)[:-2]
    return ((60*int(timeS[:2]))+int(timeS[3:]))

def testRate():
    return round(gauss(2.3,0.2),2)

def concat(entries):
    """concat(iterable) -> tab delimited table (str)"""
    return "\n".join(["\t".join([str(e) for e in entry]) for entry in entries])
    
def rateform(raw):
    if raw < 0: return str(raw)
    else: return " "+str(raw)

#Establish parameters
#Currently these need to be edited by hand for each situation.
logname = raw_input("Enter file name for log > ")
comment = raw_input("File comment? > ")
period1 = float(raw_input("Time between entries? (s) > "))
period2 = float(raw_input("Time between measurements? (s) > "))
#Might want to update this stuff to handle more user input.
#Of course, all that will go away with a GUI.
#uCoDep = raw_input("Codeposition (y/n) > ")

ser = openIC5Serial(2)
print """Opening serial port
Monitoring time, layer 1 and 2 rate and thickness.
Logging data to ./"""+logname
print """Hit Ctrl+C to end...
time\t\tagg r1\tagg r2\tavg r1\tavg r2"""
with open(logname, "w") as ffirst:
    ffirst.write("#IC/5 monitoring output\n"+\
                 comment+"\ntime(m,s)\trate1(A/s)\trate2(A/s)\n")
with open(logname,'a') as fout:
    try:
        log, i, ilast, tlast = [], 0, 0, -1
##        time, thick1, thick2 = 0, 0, 0
        while True:
            time = queryTime(ser)
            #account for wrap back of time
            #warning, only works for one loopback
            if time < tlast: treal = tlast + time
            else: treal = tlast = time
            #grab rates for averaging
            r1log, r2log = [], []
            for i in range(int((period1/period2))):
                r1log.append(queryRate(ser,1))
                r2log.append(queryRate(ser,2))
                sleep(period2)
##                rate1 = queryRate(ser,1)
##                rate2 = queryRate(ser,2)
            #averaging rates
            avgr1 = round(float(sum(r1log))/max(len(r1log),1),3)
            avgr2 = round(float(sum(r2log))/max(len(r2log),1),3)
            #grab thicknesses
            thick1 = queryThickness(ser,1)
            thick2 = queryThickness(ser,2)
            #grab aggregate rate
            aggr1 = round(thick1*1000/time,3)
            aggr2 = round(thick2*1000/time,3)
            print "\r{}\t\t{}\t{}\t{}\t{}".format(time,aggr1,aggr2,avgr1,avgr2),
            log.append((time,avgr1,avgr2,thick1,thick2))
            #Save data every five minutes.
            if (i-ilast) >= (5*60/period1):
                fout.write(concat(log[ilast:]))
                ilast = i+1
            sleep(period1)
            i += 1
    except KeyboardInterrupt:
        fout.write(concat(log[ilast:]))

print "\nClosing serial port"
ser.close()
