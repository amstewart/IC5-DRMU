"""Front end for Inficon IC/5 interface.
7.Jul.2015, by David M. Stewart"""

import wx, sys, serial
from wx.lib.pubsub import pub
from threading import Thread

import matplotlib
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import Toolbar, FigureCanvasWxAgg
from matplotlib.figure import Figure

import numpy as np

from random import gauss
from time import sleep, clock
import datetime

me = "IC5-DRMU v2015.1.b"


class BackEndThread(Thread):
    def __init__(self, parent):
        Thread.__init__(self)
        self.signal = True
        self.logevery = parent.Sets['logtime']
        self.readevery = parent.Sets['readtime']
        self.count = parent.Sets['readnum']
        self.layers = parent.Sets['layers']
        # Needs to initialize a serial object to pass to queries
        self.start()

    def run(self):
        # Needs to be updated to use serial queries
        lastTime = clock()
        self.inc = 0
        while self.signal:
            self.readL1, self.readL2, n = [], [], 0
            while n <= self.count:
                wx.CallAfter(self.query)
                n += 1
                sleep(self.readevery)
            self.rates = [round(sum(self.readL1)/len(self.readL1),3),
                          round(sum(self.readL2)/len(self.readL2),3)]
            self.thicks = [self.thic1,self.thic2]
            self.time = round(clock(),2)
            # Post it
            pub.sendMessage("ud", time=self.time, 
                            rates=self.rates, 
                            thicks=self.thicks)

    def query(self):
        self.Fake_IC5()
    # Later, these readings will be done in separate methods
        self.readL1.append(self.rate1)
        self.readL2.append(self.rate2)
    
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
    
    def Fake_IC5(self):
        # print "Fake IC5 looping"
        self.rate1 = round(gauss(0.23,0.02),3)
        self.rate2 = round(gauss(0.15,0.02),3)
        self.thic1 = round(self.rate1*self.inc*self.readevery,2)
        self.thic2 = round(self.rate2*self.inc*self.readevery,2)
        self.inc +=1

# class IC5Log():
    # def __init__(self, layers=[1]):
        # self.log = {'t':[0.0], 'toff':0.0}
        # self.layers = layers
        # for l in layers:
            # self.log[l] = {'r':[], 'l':[], 'loff':0.0}
        
    # def Update(self, )
        
        
class DRMU_Frame(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self, parent, -1,
                          title="DRMU - v2015.1.a")
        self.BuildFrame()
        
        self.axes.set_xlim(0,20,auto=True)
        self.axes.set_ylim(0,1,auto=True)
        
        self.StartBtn.Disable()
        self.PauseBtn.Disable()
        self.StopBtn.Disable()
        
        self.RatesToAvg = {}
        self.Sets = {'logtime':1.0, 'readnum':4, 'readtime':0.5,
                     'codep':False, 'logzero':True, 'zerostart':True,
                     'l1corr':1.0, 'l2corr':1.0,
                     'layers':[1],
                     'port':3, 'baud':9600}
        self.LogComments = []
        h1, h2 = self.axes.plot([],[],[],[])
        self.Traces = [h1, h2]
        
        #Done
        pub.subscribe(self.UpdateData, "ud")
        self.Show(True)
        
    def BuildFrame(self):
        
        #Create File menu
        filemenu = wx.Menu()
        fileSave = filemenu.Append(-1, "&Save log",
                                   "Save current data to file")
        fileExit = filemenu.Append(wx.ID_EXIT,"E&xit")
        #Create View menu
        viewmenu = wx.Menu()
        self.viewCoDep = viewmenu.Append(-1, "Co-dep",
                                         "Show/Hide second layer",
                                         kind=wx.ITEM_CHECK)
        self.viewCurRate = viewmenu.Append(-1, "Current Rate",
                                           "Show/Hide current raate",
                                           kind=wx.ITEM_CHECK)
        self.viewAggRate = viewmenu.Append(-1, "Aggregate Rate",
                                           "Show/Hide aggreagate rate",
                                           kind=wx.ITEM_CHECK)
        self.viewAvgRate = viewmenu.Append(-1, "Average Rate",
                                           "Show/Hide average rate",
                                           kind=wx.ITEM_CHECK)
        self.viewThick = viewmenu.Append(-1, "Thickness",
                                         "Show/Hide accumulated thickness",
                                         kind=wx.ITEM_CHECK)
        #Create Connection menu
        conmenu = wx.Menu()
        conOpen = conmenu.Append(-1, "O&pen",
                                 "Open serial connection")
        conClose = conmenu.Append(-1, "C&lose",
                                  "Close serial connection")
        #Create Logging menu
        logmenu = wx.Menu()
        logSettings = logmenu.Append(-1, "&Settings",
                                     "Change logging settings")
        logErase = logmenu.Append(-1, "&Erase Log",
                                  "Completely erase log")
        #Create menu bar
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu,"&File")
        menuBar.Append(viewmenu,"&View")
        menuBar.Append(conmenu,"&Connection")
        menuBar.Append(logmenu,"&Logging")
        self.SetMenuBar(menuBar)
        
        #Bind File events
        self.Bind(wx.EVT_MENU, self.OnExit, fileExit)
        self.Bind(wx.EVT_MENU, self.SaveLog, fileSave)
        # Bind View events
        self.Bind(wx.EVT_MENU, self.TogCoDep, self.viewCoDep)
        self.Bind(wx.EVT_MENU, self.TogCurRate, self.viewCurRate)
        self.Bind(wx.EVT_MENU, self.TogAggRate, self.viewAggRate)
        self.Bind(wx.EVT_MENU, self.TogAvgRate, self.viewAvgRate)
        self.Bind(wx.EVT_MENU, self.TogThick, self.viewThick)
        #Bind Connection events
        self.Bind(wx.EVT_MENU, self.ConSet, conOpen)
        self.Bind(wx.EVT_MENU, self.StopReading, conClose)
        #Bind Logging events
        self.Bind(wx.EVT_MENU, self.LogSet, logSettings)
        self.Bind(wx.EVT_MENU, self.InitDataLog, logErase)
        
        #Create labels for rate and thickness
        panel = wx.Panel(self, -1)
        
        LBufLbl = wx.StaticText(panel, -1, "")
        self.curLbl = wx.StaticText(panel, -1, "Current Rate (A/s)")
        self.avgLbl = wx.StaticText(panel, -1, "Average Rate (A/s)")
        self.aggLbl = wx.StaticText(panel, -1, "Aggregate Rate (A/s)")
        self.thkLbl = wx.StaticText(panel, -1, "Thickness (A)")
        self.ROLabels = [self.curLbl, self.avgLbl, self.aggLbl, self.thkLbl]
        
        L1HeadLbl = wx.StaticText(panel, -1, "Layer 1")
        self.curR1L = wx.StaticText(panel, -1, "0.000")
        self.avgR1L = wx.StaticText(panel, -1, "0.000")
        self.aggR1L = wx.StaticText(panel, -1, "0.000")
        self.thick1L = wx.StaticText(panel, -1, "0000.0")
        self.ROLayer1 = [self.curR1L, self.avgR1L, self.aggR1L, self.thick1L]
        
        L2HeadLbl = wx.StaticText(panel, -1, "Layer 2")
        self.curR2L = wx.StaticText(panel, -1, "0.000")
        self.avgR2L = wx.StaticText(panel, -1, "0.000")
        self.aggR2L = wx.StaticText(panel, -1, "0.000")
        self.thick2L = wx.StaticText(panel, -1, "0000.0")
        self.ROLayer2 = [self.curR2L, self.avgR2L, self.aggR2L, self.thick2L]
        
        self.ReadOuts = [self.ROLayer1, self.ROLayer2]
        
        self.TimeHdLbl = wx.StaticText(panel, -1, "Dep. Time")
        self.TimeROLbl = wx.StaticText(panel, -1, "00:00")

        #Create plot
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        #Margins add both left and right, but I only want right in x
        #self.axes.margins(0.5,1,tight=False)
        self.canvas = FigureCanvasWxAgg(panel, -1, self.figure)
        
        # Command buttons
        self.ZeroBtn = wx.Button(panel, -1, "Zero")
        self.StartBtn = wx.Button(panel, -1, "Start Log")
        self.PauseBtn = wx.Button(panel, -1, "Pause Log")
        self.StopBtn = wx.Button(panel, -1, "Stop Log")
        #Bind events
        self.ZeroBtn.Bind(wx.EVT_BUTTON, self.Tear)
        self.StartBtn.Bind(wx.EVT_BUTTON, self.StartLogging)
        self.PauseBtn.Bind(wx.EVT_BUTTON, self.PauseLogging)
        self.StopBtn.Bind(wx.EVT_BUTTON, self.StopLogging)
        
        #Sizers
        right, center, buf = wx.ALL|wx.ALIGN_RIGHT, wx.ALL|wx.ALIGN_CENTER, 5
        #Add to ROSizer
        commandSzr = wx.BoxSizer(wx.VERTICAL)
        commandSzr.Add(self.ZeroBtn, 0, center, buf)
        CmdDivider = wx.StaticLine(panel, -1, style=wx.LI_HORIZONTAL)
        commandSzr.Add(CmdDivider, 0, wx.EXPAND|wx.ALL, 2)
        commandSzr.Add(self.StartBtn, 0, center, buf)
        commandSzr.Add(self.PauseBtn, 0, center, buf)
        commandSzr.Add(self.StopBtn, 0, center, buf)
        
        #Read out labels
        ROFont = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                         wx.FONTWEIGHT_NORMAL)
        LbFont = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                         wx.FONTWEIGHT_NORMAL)
        HdFont = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                         wx.FONTWEIGHT_NORMAL, underline=True)
        self.ROLblSzr = wx.BoxSizer(wx.VERTICAL)
        self.ROLblSzr.Add(LBufLbl, 0, right, buf)
        LBufLbl.SetFont(HdFont)
        for l in self.ROLabels:
            self.ROLblSzr.Add(l, 0, right, buf)
            l.SetFont(ROFont)
        #Layer one readouts
        self.ROL1Szr = wx.BoxSizer(wx.VERTICAL)
        self.ROL1Szr.Add(L1HeadLbl, 0, center, buf)
        L1HeadLbl.SetFont(HdFont)
        for l in self.ROLayer1:
            self.ROL1Szr.Add(l, 0, center, buf)
            l.SetFont(ROFont)
        #Layer two readouts
        self.ROL2Szr = wx.BoxSizer(wx.VERTICAL)
        self.ROL2Szr.Add(L2HeadLbl, 0, center, buf)
        L2HeadLbl.SetFont(HdFont)
        for l in self.ROLayer2:
            self.ROL2Szr.Add(l, 0, center, buf)
            l.SetFont(ROFont)
        # Time readout
        self.TimeSzr = wx.BoxSizer(wx.VERTICAL)
        self.TimeSzr.Add(self.TimeHdLbl, 0, center, buf)
        self.TimeHdLbl.SetFont(HdFont)
        self.TimeSzr.Add(self.TimeROLbl, 0, center, buf)
        self.TimeROLbl.SetFont(ROFont)
            
        #Readouts
        SomeFlags = wx.LEFT|wx.RIGHT|wx.EXPAND|wx.ALIGN_CENTER
        self.readOutSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.readOutSizer.Add(commandSzr, 1, SomeFlags, 10)
        self.readOutSizer.Add(self.ROLblSzr, 0)
        self.readOutSizer.Add(self.ROL1Szr, 0)
        self.RODivider = wx.StaticLine(panel, -1, style=wx.LI_VERTICAL)
        self.readOutSizer.Add(self.RODivider, 0, wx.EXPAND|wx.ALL, 2)
        self.readOutSizer.Add(self.ROL2Szr, 0)        
        self.readOutSizer.Add(self.TimeSzr, 1, SomeFlags, 10)
        
        #Panel Sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.readOutSizer, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        sizer.Add(self.canvas, 1, wx.ALL|wx.ALIGN_CENTER, 5)
        panel.SetSizer(sizer)
        sizer.Fit(self)

    def TogCoDep(self, event):
        if self.viewCoDep.IsChecked():
            self.readOutSizer.Show(self.ROL2Szr)
            self.readOutSizer.Show(self.RODivider)
        else:
            self.readOutSizer.Hide(self.ROL2Szr)
            self.readOutSizer.Hide(self.RODivider)
        self.readOutSizer.Layout()
        
    def TogCurRate(self, event):
        if self.viewCurRate.IsChecked():
            self.ROLblSzr.Show(self.curLbl)
            self.ROL1Szr.Show(self.curR1L)
            if self.viewCoDep.IsChecked(): self.ROL2Szr.Show(self.curR2L)
        else:
            self.ROLblSzr.Hide(self.curLbl)
            self.ROL1Szr.Hide(self.curR1L)
            self.ROL2Szr.Hide(self.curR2L)
        self.readOutSizer.Layout()
        
    def TogAggRate(self, event):
        if self.viewAggRate.IsChecked():
            self.ROLblSzr.Show(self.aggLbl)
            self.ROL1Szr.Show(self.aggR1L)
            if self.viewCoDep.IsChecked(): self.ROL2Szr.Show(self.aggR2L)
        else:
            self.ROLblSzr.Hide(self.aggLbl)
            self.ROL1Szr.Hide(self.aggR1L)
            self.ROL2Szr.Hide(self.aggR2L)
        self.readOutSizer.Layout()

    def TogAvgRate(self, event):
        if self.viewAvgRate.IsChecked():
            self.ROLblSzr.Show(self.avgLbl)
            self.ROL1Szr.Show(self.avgR1L)
            if self.viewCoDep.IsChecked(): self.ROL2Szr.Show(self.avgR2L)
        else:
            self.ROLblSzr.Hide(self.avgLbl)
            self.ROL1Szr.Hide(self.avgR1L)
            self.ROL2Szr.Hide(self.avgR2L)
        self.readOutSizer.Layout()
        
    def TogThick(self, event):
        if self.viewThick.IsChecked():
            self.ROLblSzr.Show(self.thkLbl)
            self.ROL1Szr.Show(self.thick1L)
            if self.viewCoDep.IsChecked(): self.ROL2Szr.Show(self.thick2L)
        else:
            self.ROLblSzr.Hide(self.thkLbl)
            self.ROL1Szr.Hide(self.thick1L)
            self.ROL2Szr.Hide(self.thick2L)
        self.readOutSizer.Layout()

    def StopReading(self, event):
        self.BET.signal = False
        
    def LogSet(self, event):
        setings = DRMU_Settings(self)

    def ConSet(self, event):
        connection = DRMU_Serial(self)
        
    def InitDataLog(self):
        # print "Initing DataLog"
        self.DataLog = {'t':[], 'toff':0.0}
        for layer in self.Sets['layers']:
            self.DataLog[layer] = {'r':[], 'l':[], 'loff':0.0}
        self.iStart, self.iStop = 0, 0
        
    # def UpdateReadOut(self, readout, curR, avgR, aggR, thik)
    def UpdateData(self, time, rates, thicks):
        # Update the time vector
        self.DataLog['t'].append(time)
        offTime = time + self.DataLog['toff']
        self.TimeROLbl.SetLabel(str(offTime))
        
        # Loop to update everything for the layers
        # This should loop at most twice
        for i in range(len(self.Sets['layers'])):
            # len(Sets['layers']) = 1 or 2
            l = self.Sets['layers'][i]
            # Store layer data to DataLog
            self.DataLog[l]['r'].append(rates[i])
            self.DataLog[l]['l'].append(thicks[i])
            # Keep last n(=10) rates for averaging
            try:
                self.RatesToAvg[i].append(rates[i])
                if len(self.RatesToAvg[i]) > 10:
                    self.RatesToAvg[i] = self.RatesToAvg[i][1:]
            except KeyError:
                self.RatesToAvg[i] = [rates[i]]
            # Update ReadOuts
            # Calculate non-current rates
            avgRate = round(sum(self.RatesToAvg[i])/len(self.RatesToAvg[i]),3)
            offThick = thicks[i] + self.DataLog[l]['loff']
            aggRate = round(offThick/offTime, 3)
            # ReadOuts[i] = [curR, avgR, aggR, thick] <- wx.StaticTexts
            self.ReadOuts[i][0].SetLabel(str(rates[i]))
            self.ReadOuts[i][1].SetLabel(str(avgRate))
            self.ReadOuts[i][2].SetLabel(str(aggRate))
            self.ReadOuts[i][3].SetLabel(str(offThick))
            # Update graph
            self.Traces[i].set_xdata(self.DataLog['t'])
            self.Traces[i].set_ydata(self.DataLog[l]['r'])
        
        self.axes.relim()
        self.axes.autoscale_view()
        self.canvas.draw()
        
        if self.FirstUpdate:
            self.StartBtn.Enable()
            self.FirstUpdate = False
        
    def Tear(self, event):
        # Set offsets to zero all thicknesses and time.
        pass
    
    def StartLogging(self,event):
        # For event recording, grab the time and the point in the log
        time = self.DataLog['t'][-1]
        t = len(self.DataLog['t'])
        # Log the start time and write a comment
        self.LogComments.append((t, time, "#{}: Log began.".format(time)))
        self.iStart = t
        if self.Sets['zerostart']:
            # Set a time offset
            self.DataLog['toff'] = -time
            self.LogComments.append((t, time,
                                    "#{}: Time offset by {} s.".format(time,
                                                        self.DataLog['toff'])))
            for l in self.Sets['layers']:
                # Set layer thickness offset
                self.DataLog[l]['loff'] = -self.DataLog[l]['l'][-1]
                self.LogComments.append((t, time,
                    "#{}:Layer {} thickness offset by {} A.".format(time,
                        l, self.DataLog[l]['loff'])))
                self.DataLog[l]['loff']
        
        # self.OnStart = True
        self.StartBtn.Disable()
        # self.PauseBtn.Enable()
        self.StopBtn.Enable()
    
    def PauseLogging(self, event):
        # self.logging = False
        # self.PauseBtn.Disable()
        # self.StartBtn.Enable()
        pass
        
    def StopLogging(self, event):
        # For event recording, grab the time and the point in the log
        time = self.DataLog['t'][-1]
        t = len(self.DataLog['t'])
        # Log the start time and write a comment
        self.LogComments.append((t, time, "#{}: Log ended.".format(time)))
        self.iStop = t
        self.StartBtn.Enable()
        self.StopBtn.Disable()
        # self.PauseBtn.Enable()

    def SaveLog(self, event):
        # Write a file of DataLog between StartStop points
        # Ask where to save it
        s = wx.FD_SAVE|wx.FD_CHANGE_DIR|wx.FD_OVERWRITE_PROMPT
        dlg = wx.FileDialog(self, "Save deposition log", 
                            wildcard = "Log files (*.log)|*.log|"+\
                                       "Text files (*.txt)|*.txt",
                            style = s)
        if dlg.ShowModal() == wx.ID_OK:
            # Grab comments
            toWrite = "#Log written by {}\n#{}\n".format(me,
                                                datetime.datetime.now())
            toWrite += "\n".join(c for (t,tt,c) in self.LogComments)+"\n"
            # Make data table
            table = ["time(s)"]
            for l in self.Sets['layers']:
                # Make the header
                table[0] += "\trate {}(A/s)\tthickness {}(A)".format(l,l)
                # StartStop = (start index, stop index)
            for i in range(self.iStart, self.iStop+1):
                # Make the data rows
                items = [str(self.DataLog['t'][i]+self.DataLog['toff'])]
                for l in self.Sets['layers']:
                    items += [str(self.DataLog[l]['r'][i]),
                              str(self.DataLog[l]['l'][i]+\
                              self.DataLog[l]['loff'])]
                table.append("\t".join(items))
            # Finalize and save
            toWrite += "\n".join(table)
            with open(dlg.GetPath(), 'w') as fout:
                fout.write(toWrite)
        dlg.Destroy()
        print "Start: {}, Stop: {}".format(self.iStart, self.iStop)
        
    def OnExit(self,e):
        self.Close(True)

class DRMU_Settings(wx.Frame):
    def __init__(self, parent):
        no_resize = wx.CAPTION|wx.SYSTEM_MENU|wx.CLIP_CHILDREN|\
                    wx.FRAME_NO_TASKBAR|wx.CLOSE_BOX
        wx.Frame.__init__(self, parent, -1, style=no_resize,
                          title="DRMU - User Settings")
        self.parent = parent
        panel = wx.Panel(self, -1)
        
        #Labels for TextControls
        logtimeLbl = wx.StaticText(panel, -1, 
                                   "Time between logging (s)")
        readnumLbl = wx.StaticText(panel, -1, 
                                   "Rate readings to average")
        readtimeLbl = wx.StaticText(panel, -1, 
                                    "Time between readings (s)")
        corrtopLbl = wx.StaticText(panel, -1,
                                   "Rate and Thickness correction factors")
        corrL1Lbl = wx.StaticText(panel, -1, "Layer 1:")
        corrL2Lbl = wx.StaticText(panel, -1, "Layer 2:")
        
        #TextControls
        txt_sz = (40,20)
        self.logtimeTxt = wx.TextCtrl(panel, -1, size=txt_sz)
        self.readnumTxt = wx.TextCtrl(panel, -1, size=txt_sz)
        self.readtimeTxt = wx.TextCtrl(panel, -1, size=txt_sz)
        self.corrL1Txt = wx.TextCtrl(panel, -1, size=txt_sz)
        self.corrL2Txt = wx.TextCtrl(panel, -1, size=txt_sz)
        
        self.codepChk = wx.CheckBox(panel, -1, "Monitor codeposition",
                                    style=wx.ALIGN_RIGHT)
        self.logZeroChk = wx.CheckBox(panel, -1, "Log zeroing events",
                                    style=wx.ALIGN_RIGHT)
        self.zeroStartChk = wx.CheckBox(panel, -1, "Zero log on start",
                                        style=wx.ALIGN_RIGHT)
        okayBtn = wx.Button(panel, -1, "Okay")
        
        #Sizers
        right, left, buf = wx.ALL|wx.ALIGN_RIGHT, wx.ALL|wx.ALIGN_LEFT, 3
        timingSzr = wx.FlexGridSizer(3,2,3,3)
        timingSzr.SetFlexibleDirection(wx.HORIZONTAL)
        timingSzr.Add(logtimeLbl, 0, right, buf)
        timingSzr.Add(self.logtimeTxt, 0, left, buf)
        timingSzr.Add(readnumLbl, 0, right, buf)
        timingSzr.Add(self.readnumTxt, 0, left, buf)
        timingSzr.Add(readtimeLbl, 0, right, buf)
        timingSzr.Add(self.readtimeTxt, 0, left, buf)
        
        corrSzr = wx.BoxSizer(wx.HORIZONTAL)
        corrSzr.Add(corrL1Lbl, 0, right, buf)
        corrSzr.Add(self.corrL1Txt, 0, left, buf)
        corrSzr.Add(corrL2Lbl, 0, right, buf)
        corrSzr.Add(self.corrL2Txt, 0, left, buf)
        
        layerSzr = wx.BoxSizer(wx.VERTICAL)
        layerSzr.Add(corrtopLbl, 0, wx.ALL|wx.ALIGN_LEFT, buf)
        layerSzr.Add(corrSzr)
        
        #Events
        okayBtn.Bind(wx.EVT_BUTTON, self.OkayClose)
        self.logtimeTxt.Bind(wx.EVT_KILL_FOCUS, self.LogTimeUpDate,
                             self.logtimeTxt)
        self.readnumTxt.Bind(wx.EVT_KILL_FOCUS, self.ReadNumUpDate,
                             self.readnumTxt)
        self.readtimeTxt.Bind(wx.EVT_KILL_FOCUS, self.ReadTimeUpDate, 
                              self.readtimeTxt)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(timingSzr)
        sizer.Add(self.codepChk, 0, wx.ALL|wx.ALIGN_LEFT, 5)
        sizer.Add(self.logZeroChk, 0, wx.ALL|wx.ALIGN_LEFT, 5)
        sizer.Add(self.zeroStartChk, 0, wx.ALL|wx.ALIGN_LEFT, 5)
        sizer.Add(layerSzr)
        sizer.Add(okayBtn)
        panel.SetSizer(sizer)
        sizer.Fit(self)
        
        #Initialize TextCtrls from parent.Sets
        self.logtimeTxt.SetValue(str(parent.Sets['logtime']))
        self.readnumTxt.SetValue(str(parent.Sets['readnum']))
        self.readtimeTxt.SetValue(str(parent.Sets['readtime']))
        self.codepChk.SetValue(parent.Sets['codep'])
        self.logZeroChk.SetValue(parent.Sets['logzero'])
        self.zeroStartChk.SetValue(parent.Sets['zerostart'])
        self.corrL1Txt.SetValue(str(parent.Sets['l1corr']))
        self.corrL2Txt.SetValue(str(parent.Sets['l2corr']))
        
        self.Show()
        
    def OkayClose(self,event):
        #update settings and close
        self.parent.Sets['logtime'] = float(self.logtimeTxt.GetValue())
        self.parent.Sets['readnum'] = int(self.readnumTxt.GetValue())
        self.parent.Sets['readtime']= float(self.readtimeTxt.GetValue())
        self.parent.Sets['codep']= self.codepChk.GetValue()
        if self.parent.Sets['codep']: self.parent.Sets['layers'] = [1,2]
        else: self.parent.Sets['layers'] = [1]
        self.parent.Sets['logzero']= self.logZeroChk.GetValue()
        self.parent.Sets['zerostart']= self.zeroStartChk.GetValue()
        self.parent.Sets['l1corr'] = float(self.corrL1Txt.GetValue())
        self.parent.Sets['l2corr'] = float(self.corrL2Txt.GetValue())
        # top = wx.GetApp().GetTopWindow()
        # top.Close()       
        self.Close(True)
        
    def LogTimeUpDate(self, event):
        logT = float(self.logtimeTxt.GetValue())
        readT = round(float(self.readtimeTxt.GetValue()),3)
        if readT > logT:
            self.readtimeTxt.SetValue(str(logT))
            self.readnumTxt.SetValue("1")
        else:
            self.readnumTxt.SetValue(str(int(logT/readT)))
        event.Skip()
            
    def ReadNumUpDate(self, event):
        logT = float(self.logtimeTxt.GetValue())
        readT = round(float(self.readtimeTxt.GetValue()),3)
        readN = int(self.readnumTxt.GetValue())
        if readT > logT:
            self.readtimeTxt.SetValue(str(logT))
            self.readnumTxt.SetValue("1")
        else:
            t = round(logT/readN,3)
            self.readtimeTxt.SetValue(str(t))
        event.Skip()
            
    def ReadTimeUpDate(self, event):
        logT = float(self.logtimeTxt.GetValue())
        readT = round(float(self.readtimeTxt.GetValue()),3)
        if readT > logT:
            self.readtimeTxt.SetValue(str(logT))
            self.readnumTxt.SetValue("1")
        else:
            self.readtimeTxt.SetValue(str(readT))
            self.readnumTxt.SetValue(str(int(logT/readT)))
        event.Skip()
    
    def OnExit(self,e):
        self.Close(True)
       
class DRMU_Serial(wx.Frame):
    def __init__(self, parent):
        no_resize = wx.CAPTION|wx.SYSTEM_MENU|wx.CLIP_CHILDREN|\
                    wx.FRAME_NO_TASKBAR|wx.CLOSE_BOX
        self.parent = parent
        wx.Frame.__init__(self, parent, -1, style=no_resize,
                          title="DRMU - Serial Settings")
        panel = wx.Panel(self, -1)
        
        sernumLbl = wx.StaticText(panel, -1, "Serial port")
        baudrtLbl = wx.StaticText(panel, -1, "Baud rate")
        
        self.sernumSpn = wx.SpinCtrl(panel, size=(40,-1), max=20)
        self.baudrtTxt = wx.TextCtrl(panel, size=(40,20))
        
        testBtn = wx.Button(panel, -1, "Test")
        cnctBtn = wx.Button(panel, -1, "Connect")
        
        self.sernumSpn.SetValue(parent.Sets['port'])
        self.baudrtTxt.SetValue(str(parent.Sets['baud']))
        
        testBtn.Bind(wx.EVT_BUTTON, self.TestConn)
        cnctBtn.Bind(wx.EVT_BUTTON, self.Connect)
        
        right, left, buf = wx.ALL|wx.ALIGN_RIGHT, wx.ALL|wx.ALIGN_LEFT, 3
        sizer = wx.FlexGridSizer(3,2,3,3)
        sizer.SetFlexibleDirection(wx.HORIZONTAL)
        sizer.Add(sernumLbl, 0, right, buf)
        sizer.Add(self.sernumSpn, 0, left, buf)
        sizer.Add(baudrtLbl, 0, right, buf)
        sizer.Add(self.baudrtTxt, 0, left, buf)
        sizer.Add(testBtn, 0, wx.ALL|wx.ALIGN_CENTER, 3)
        sizer.Add(cnctBtn, 0, wx.ALL|wx.ALIGN_CENTER, 3)
        
        panel.SetSizer(sizer)
        sizer.Fit(self)
        self.Show()
        
    def TestConn(self, event):
        # port = self.sernumSpn.GetValue()
        # baud = int(self.baudrtTxt.GetValue())
        # ser = serial.Serial(port,baud,rtscts=True,timeout=1)
        # ser.write("H\xo6")
        # ser.read()
        result = wx.MessageDialog(self, "Not implemented",
                                  "IC5 Serial Test",
                                  wx.OK|wx.STAY_ON_TOP)
        result.ShowModal()
        
    def Connect(self, event):
        # self.parent.BET = BackEndThread(self.sernumSpn.GetValue(),
                                       # int(self.baudrtTxt.GetValue()),
                                       # self.parent.Sets['logtime'],
                                       # self.parent.Sets['readtime'],
                                       # self.parent.Sets['readnum'])
        # Initialize the data log and begin the backend thread
        self.parent.InitDataLog()
        self.parent.Sets['port'] = self.sernumSpn.GetValue()
        self.parent.Sets['baud'] = int(self.baudrtTxt.GetValue())
        self.parent.BET = BackEndThread(self.parent)
        # Don't enable the start button until after the first data read
        # self.parent.StartBtn.Enable()
        self.parent.FirstUpdate = True
        self.Close(True)
        
    def OnExit(self,e):
        self.Close(True)    
       
app = wx.App(False)
frame = DRMU_Frame(None)
app.MainLoop()
