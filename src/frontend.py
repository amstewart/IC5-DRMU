"""Front end for Inficon IC/5 interface.
15.Jul.2015, by David M. Stewart"""

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

me = "IC5-DRMU v2015.2.a"


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

class DRMU_Frame(wx.Frame):
    def __init__(self, parent):
        no_resize = wx.DEFAULT_FRAME_STYLE & ~ (wx.RESIZE_BORDER | 
                                                wx.RESIZE_BOX | 
                                                wx.MAXIMIZE_BOX)
        wx.Frame.__init__(self, parent, -1, style=no_resize,
                          title=me+" - Main")
        
        self.RatesToAvg = {}
        self.Sets = {'showcur':True, 'showavg':True, 'showagg':True,
                     'showthick':True, 'logzero':True, 'zerostart':True,
                     'tgtthick':0.0, 'codep':True, 'layers':[1,2],
                     'mat1name':"", 'mat1rate':0.0, 'mat1corr':1.0,
                     'mat2name':"", 'mat2rate':0.0, 'mat2corr':1.0, 
                     'primemat':0, 'tgtcomp':100.0,
                     'port':3, 'baud':9600,
                     'logtime':1.0, 'readnum':4, 'readtime':0.25,
                     'depsamp':5.0}
        self.LogComments = []
        
        
        self.BuildFrame()
        self.Graphs = DRMU_Graphs(self)
        self.UpdateView()
        
        # self.axes.set_xlim(0,20,auto=True)
        # self.axes.set_ylim(0,1,auto=True)
        # h1, h2 = self.axes.plot([],[],[],[])
        # self.Traces = [h1, h2]
        
        #Done
        pub.subscribe(self.UpdateData, "ud")
        self.Show(True)
        
    def BuildFrame(self):
        menu = wx.Menu()
        settMenu = menu.Append(-1, "Settings", "Change user settings")
        connMenu = menu.Append(-1, "Connect", "Begin querying the IC/5")
        discMenu = menu.Append(-1, "Disconnect", "Stop querying the IC/5")
        # commMenu = menu.Append(-1, "Log Comments", "Open log comments dialog")
        saveMenu = menu.Append(-1, "Save Log", "Save a completed log")
        # tearMenu = menu.Append(-1, "Erase Log", "Completely erase the log")
        exitMenu = menu.Append(-1, "Exit", "Close the program")
        
        # Bind menu events
        self.Bind(wx.EVT_MENU, self.OpenSettings, settMenu)
        self.Bind(wx.EVT_MENU, self.OnConnect, connMenu)
        self.Bind(wx.EVT_MENU, self.OnDisconnect, discMenu)
        # self.Bind(wx.EVT_MENU, self.OpenComments, commMenu)
        self.Bind(wx.EVT_MENU, self.SaveLog, saveMenu)
        # self.Bind(wx.EVT_MENU, self.Tear, tearMenu)
        self.Bind(wx.EVT_MENU, self.OnExit, exitMenu)

        menuBar = wx.MenuBar()
        menuBar.Append(menu, "Menu")
        self.SetMenuBar(menuBar)
        
        panel = wx.Panel(self, -1)
        panSzr = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(panSzr)

        # Command Buttons
        BtnFlags = wx.ALL|wx.ALIGN_TOP|wx.ALIGN_CENTER_HORIZONTAL
        ButtonSzr = wx.BoxSizer(wx.HORIZONTAL)
        self.StartBtn = wx.Button(panel, -1, "Start")
        self.PauseBtn = wx.Button(panel, -1, "Pause")
        self.StopBtn = wx.Button(panel, -1, "Stop")
        self.ZeroBtn = wx.Button(panel, -1, "Zero")
        # Bind button events
        self.StartBtn.Bind(wx.EVT_BUTTON, self.StartLogging)
        # self.PauseBtn.Bind(wx.EVT_BUTTON, self.PauseLogging)
        self.StopBtn.Bind(wx.EVT_BUTTON, self.StopLogging)
        # self.ZeroBtn.Bind(wx.EVT_BUTTON, self.ZeroLog)
        
        ButtonSzr.AddStretchSpacer(1)
        ButtonSzr.AddMany([(self.StartBtn, 0, BtnFlags, 5),
                           (self.PauseBtn, 0, BtnFlags, 5),
                           (self.StopBtn, 0, BtnFlags, 5),
                           (self.ZeroBtn, 0, BtnFlags, 5)])
        ButtonSzr.AddStretchSpacer(1)
        panSzr.Add(ButtonSzr, 0,
                   wx.TOP|wx.BOTTOM|wx.ALIGN_CENTER|wx.EXPAND, 5)

        # Fonts
        FSW = [wx.DEFAULT, wx.NORMAL, wx.NORMAL]
        HdFont = wx.Font(11, *FSW)
        BigROFont = wx.Font(13, *FSW)
        SmlROFont = wx.Font(12, *FSW)
        LblFont = wx.Font(10, *FSW)

        # Time, Thickness, and Composition read outs ----------------------
        timeLbl = wx.StaticText(panel, -1, "Deposition\nTime",
                                style=wx.ALIGN_CENTER)
        thicLbl = wx.StaticText(panel, -1, "Accumulated\nThickness",
                                style=wx.ALIGN_CENTER)
        compLbl = wx.StaticText(panel, -1, "Average Film\nComposition",
                                style=wx.ALIGN_CENTER)
        timeLbl.SetFont(HdFont)
        thicLbl.SetFont(HdFont)
        compLbl.SetFont(HdFont)
        
        self.timeRO = wx.StaticText(panel, -1, "00:00", style=wx.ALIGN_CENTER)
        self.thicRO = wx.StaticText(panel, -1, "0,000 A", style=wx.ALIGN_CENTER)
        self.compRO = wx.StaticText(panel, -1, "00.00% "+self.Sets['mat1name'],
                                    style=wx.ALIGN_CENTER)
        self.timeRO.SetFont(BigROFont)
        self.thicRO.SetFont(BigROFont)
        self.compRO.SetFont(BigROFont)
        
        timeSzr = wx.BoxSizer(wx.VERTICAL)
        thicSzr = wx.BoxSizer(wx.VERTICAL)
        compSzr = wx.BoxSizer(wx.VERTICAL)
        BigROItemFlags = wx.EXPAND|wx.ALIGN_TOP|wx.ALIGN_CENTER_HORIZONTAL
        timeSzr.AddMany([(timeLbl, 0, wx.EXPAND|wx.ALIGN_TOP\
                          |wx.ALIGN_CENTER_HORIZONTAL|wx.BOTTOM, 6),
                         (self.timeRO, 0, BigROItemFlags, 0)])
        thicSzr.AddMany([(thicLbl, 0, wx.EXPAND|wx.ALIGN_TOP\
                          |wx.ALIGN_CENTER_HORIZONTAL|wx.BOTTOM, 6),
                         (self.thicRO, 0, BigROItemFlags, 0)])
        compSzr.AddMany([(compLbl, 0, wx.EXPAND|wx.ALIGN_TOP\
                          |wx.ALIGN_CENTER_HORIZONTAL|wx.BOTTOM, 6),
                         (self.compRO, 0, BigROItemFlags, 0)])
        
        self.BigROSzr = wx.BoxSizer(wx.HORIZONTAL)
        BigROFlags = wx.LEFT|wx.RIGHT|wx.EXPAND|wx.ALIGN_TOP|wx.ALIGN_CENTER_HORIZONTAL
        self.BigROSzr.AddStretchSpacer(1)
        self.BigROSzr.AddMany([(timeSzr, 0, BigROFlags, 20),
                              (thicSzr, 0, BigROFlags, 20),
                              (compSzr, 0, BigROFlags, 20)])
        self.BigROSzr.AddStretchSpacer(1)
        
        # Layer rates and thickness readouts -----------------------------
        self.Mat1Lbl = wx.StaticText(panel, -1, self.Sets['mat1name'],
                                     style=wx.ALIGN_CENTER)
        self.Mat2Lbl = wx.StaticText(panel, -1, self.Sets['mat2name'],
                                     style=wx.ALIGN_CENTER)
        self.Mat1Lbl.SetFont(LblFont)
        self.Mat2Lbl.SetFont(LblFont)

        blank1 = wx.StaticText(panel, -1, "", style=wx.ALIGN_RIGHT)
        blank2 = wx.StaticText(panel, -1, "", style=wx.ALIGN_RIGHT)
        self.avgRLbl = wx.StaticText(panel, -1, "Average Rate (A/s)",
                                     style=wx.ALIGN_RIGHT)
        self.curRLbl = wx.StaticText(panel, -1, "Current Rate (A/s)",
                                     style=wx.ALIGN_RIGHT)
        self.aggRLbl = wx.StaticText(panel, -1, "Aggregate Rate (A/s)",
                                     style=wx.ALIGN_RIGHT)
        self.thicLbl = wx.StaticText(panel, -1, "Thickness (A)",
                                     style=wx.ALIGN_RIGHT)
        blank1.SetFont(LblFont)
        blank2.SetFont(LblFont)
        self.avgRLbl.SetFont(LblFont)
        self.curRLbl.SetFont(LblFont)
        self.aggRLbl.SetFont(LblFont)
        self.thicLbl.SetFont(LblFont)

        SmlROStyle, SmlROBuff = wx.ALIGN_CENTER|wx.EXPAND|wx.ALL, 5

        self.M1avgRRO = wx.StaticText(panel, -1, "0.000", style=wx.ALIGN_CENTER)
        self.M1curRRO = wx.StaticText(panel, -1, "0.000", style=wx.ALIGN_CENTER)
        self.M1aggRRO = wx.StaticText(panel, -1, "0.000", style=wx.ALIGN_CENTER)
        self.M1thicRO = wx.StaticText(panel, -1, "0000", style=wx.ALIGN_CENTER)
        self.Mat1ROs = [self.M1avgRRO, self.M1curRRO,
                        self.M1aggRRO, self.M1thicRO]
        for l in self.Mat1ROs:
            l.SetFont(SmlROFont)

        self.M2avgRRO = wx.StaticText(panel, -1, "0.000", style=wx.ALIGN_CENTER)
        self.M2curRRO = wx.StaticText(panel, -1, "0.000", style=wx.ALIGN_CENTER)
        self.M2aggRRO = wx.StaticText(panel, -1, "0.000", style=wx.ALIGN_CENTER)
        self.M2thicRO = wx.StaticText(panel, -1, "0000", style=wx.ALIGN_CENTER)
        self.Mat2ROs = [self.M2avgRRO, self.M2curRRO, 
                        self.M2aggRRO, self.M2thicRO]
        for l in self.Mat2ROs:
            l.SetFont(SmlROFont)
            
        # Store all readouts to a suitable place ------------------------------
        self.ReadOuts = [self.Mat1ROs, self.Mat2ROs]

        bar1 = wx.StaticLine(panel, -1., style=wx.LI_HORIZONTAL)
        bar2 = wx.StaticLine(panel, -1., style=wx.LI_HORIZONTAL)
        self.SmlROSzr = wx.FlexGridSizer(6, 3, 3, 3)
        self.SmlROSzr.AddMany([(blank1, 0, SmlROStyle, SmlROBuff),
                               (self.Mat1Lbl, 1, SmlROStyle, SmlROBuff),
                               (self.Mat2Lbl, 1, SmlROStyle, SmlROBuff),
                               (self.avgRLbl, 0, SmlROStyle, SmlROBuff),
                               (self.M1avgRRO, 1, SmlROStyle, SmlROBuff),
                               (self.M2avgRRO, 1, SmlROStyle, SmlROBuff),
                               (self.curRLbl, 0, SmlROStyle, SmlROBuff),
                               (self.M1curRRO, 1, SmlROStyle, SmlROBuff),
                               (self.M2curRRO, 1, SmlROStyle, SmlROBuff),
                               (self.aggRLbl, 0, SmlROStyle, SmlROBuff),
                               (self.M1aggRRO, 1, SmlROStyle, SmlROBuff),
                               (self.M2aggRRO, 1, SmlROStyle, SmlROBuff),
                               (self.thicLbl, 0, SmlROStyle, SmlROBuff),
                               (self.M1thicRO, 1, SmlROStyle, SmlROBuff),
                               (self.M2thicRO, 1, SmlROStyle, SmlROBuff)])
        
        # Combine readout sizers and add to panel ----------------------------
        panSzr.AddMany([(self.BigROSzr, 0,
                         wx.ALL|wx.ALIGN_TOP|wx.ALIGN_CENTER_HORIZONTAL, 10),
                        (self.SmlROSzr, 1,
                         wx.ALL|wx.ALIGN_TOP|wx.ALIGN_CENTER_HORIZONTAL, 10)])
        panSzr.Fit(self)
        #self.Fit()
        
    def OpenSettings(self, event):
        drmuSettings = DRMU_Settings(self)
        
    def UpdateView(self):
        # Read settings and alter the windows to user specifications
        
        codep = self.Sets['codep']
        
        if codep:
            self.SmlROSzr.Show(self.Mat2Lbl)
        else:
            self.SmlROSzr.Hide(self.Mat2Lbl)
            self.SmlROSzr.Hide(self.M2avgRRO)
            self.SmlROSzr.Hide(self.M2curRRO)
            self.SmlROSzr.Hide(self.M2aggRRO)
            self.SmlROSzr.Hide(self.M2thicRO)
            
        self.Mat1Lbl.SetLabel(self.Sets['mat1name'])
        self.Mat2Lbl.SetLabel(self.Sets['mat2name'])
            
        if self.Sets['showavg']:
            self.SmlROSzr.Show(self.M1avgRRO)
            if codep: self.SmlROSzr.Show(self.M2avgRRO)
        else:
            self.SmlROSzr.Hide(self.avgRLbl)
            self.SmlROSzr.Hide(self.M1avgRRO)
            self.SmlROSzr.Hide(self.M2avgRRO)
        
        if self.Sets['showcur']:
            self.SmlROSzr.Show(self.M1curRRO)
            if codep: self.SmlROSzr.Show(self.M2curRRO)
        else:
            self.SmlROSzr.Hide(self.curRLbl)
            self.SmlROSzr.Hide(self.M1curRRO)
            self.SmlROSzr.Hide(self.M2curRRO)
            
        if self.Sets['showagg']:
            self.SmlROSzr.Show(self.M1aggRRO)
            if codep: self.SmlROSzr.Show(self.M2aggRRO)
        else:
            self.SmlROSzr.Hide(self.aggRLbl)
            self.SmlROSzr.Hide(self.M1aggRRO)
            self.SmlROSzr.Hide(self.M2aggRRO)
            
        if self.Sets['showthick']:
            self.SmlROSzr.Show(self.M1thicRO)
            if codep: self.SmlROSzr.Show(self.M2thicRO)
        else:
            self.SmlROSzr.Hide(self.thicLbl)
            self.SmlROSzr.Hide(self.M1thicRO)
            self.SmlROSzr.Hide(self.M2thicRO)
            
        self.SmlROSzr.Layout()
        
        # For beta testing, disable the buttons
        self.StartBtn.Disable()
        self.PauseBtn.Disable()
        self.StopBtn.Disable()
        self.ZeroBtn.Disable()

    def OnConnect(self, event):
        self.InitDataLog()
        self.BET = BackEndThread(self)
        self.FirstUpdate = True
        
    def OnDisconnect(self, event):
        if self.BET: self.BET.signal = False

    # def StopReading(self, event):
        # self.BET.signal = False
        
    # def LogSet(self, event):
        # setings = DRMU_Settings(self)

    # def ConSet(self, event):
        # connection = DRMU_Serial(self)
        
    def InitDataLog(self):
        self.DataLog = {'t':[], 'toff':0.0}
        for layer in self.Sets['layers']:
            self.DataLog[layer] = {'r':[], 'l':[], 'loff':0.0}
        self.iStart, self.iStop = -1, -1
        self.LastThicks = [0.0, 0.0]
        self.CompLog = {'l':[], 'c':[]}
        
    def UpdateData(self, time, rates, thicks):
        # Update the time vector
        self.DataLog['t'].append(time)
        offTime = time + self.DataLog['toff']
        self.timeRO.SetLabel(str(offTime))
        
        AccThick = 0
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
            AccThick += offThick
            # ReadOuts[i] = [curR, avgR, aggR, thick] <- wx.StaticTexts
            self.ReadOuts[i][0].SetLabel(str(rates[i]))
            self.ReadOuts[i][1].SetLabel(str(avgRate))
            self.ReadOuts[i][2].SetLabel(str(aggRate))
            self.ReadOuts[i][3].SetLabel(str(offThick))# Update graph
            # self.Traces[i].set_xdata(self.DataLog['t'])
            # self.Traces[i].set_ydata(self.DataLog[l]['r'])
            # Update rate curves in Graphs window
            self.Graphs.RateTraces[i].set_xdata(self.DataLog['t'])
            self.Graphs.RateTraces[i].set_ydata(self.DataLog[l]['r'])
        
        # Continue updating rate curves
        self.Graphs.RvTaxes.relim()
        self.Graphs.RvTaxes.autoscale_view()
        self.Graphs.RvTcanvas.draw()
        
        self.thicRO.SetLabel(str(round(AccThick,1))+" A")
        
        # Update composition
        if self.Sets['codep']:
            p = self.Sets['layers'][self.Sets['primemat']]
            if self.Sets['primemat'] = 0: pName = self.Sets['mat1name']
            else: pName = self.Sets['mat2name']
            pThick = self.DataLog[p]['l'][-1] + self.DataLog[p]['loff']
            AvgComp = round(pThick/AccThick*100, 2)
            self.compRO.SetLabel(str(AvgComp)+"% "+pName])
            if (AccThick - self.LastThicks[0]) >= self.Sets['depsamp']:
                #LastThicks = [AccThick, pThick]
                # do calcs for composition curve
                newComp = round((pThick-self.LastThicks[1])/\
                                (AccThick-self.LastThicks[0])*100, 2)
                # update CompLog and throw to Graphs window
                self.CompLog['l'].append(AccThick)
                self.CompLog['c'].append(newComp)
                self.Graphs.CompTrace.set_xdata(self.CompLog['l'])
                self.Graphs.CompTrace.set_ydata(self.CompLog['c'])
                self.Graphs.CvTaxes.relim()
                self.Graphs.CvTaxes.autoscale_view()
                self.Graphs.CvTcanvas.draw()
                # Update LastThicks
                self.LastThicks[0] = AccThick
                self.LastThicks[1] = pThick
        
        if self.FirstUpdate:
            self.StartBtn.Enable()
            self.FirstUpdate = False
        
    def Tear(self, event):
        # Set offsets to zero all thicknesses and time.
        pass
    
    def StartLogging(self, event):
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
        if self.iStart < 0:
            prompt = wx.MessageDialog(self, "No log to save",
                                  "IC5 Save Log",
                                  wx.OK|wx.STAY_ON_TOP)
            prompt.ShowModal()
            return
        else:
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
        
    def OnExit(self,e):
        try: self.BET.signal = False
        except AttributeError: pass
        self.Graphs.OnExit(None)
        self.Close(True)
        
class DRMU_Graphs(wx.Frame):
    def __init__(self, parent):
        no_close = wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER|\
                   wx.SYSTEM_MENU | wx.CAPTION | wx.CLIP_CHILDREN
        wx.Frame.__init__(self, parent, -1, style=no_close,
                          title=me+" - Graphs")
        self.parent = parent
        self.BuildFrame()
        
        self.RvTaxes.set_xlim(0, 20, auto=True)
        self.RvTaxes.set_ylim(0, 1, auto=True)
        hR1, hR2 = self.RvTaxes.plot([],[],[],[])
        self.RateTraces = [hR1, hR2]
        
        self.CvTaxes.set_xlim(0, 20, auto=True)
        self.CvTaxes.set_ylim(0, 100, auto=False)
        self.CompTrace, = self.CvTaxes.plot([],[])
        
        if self.parent.Sets['codep']:
            self.panSzr.Show(self.CvTcanvas)
            self.panSzr.Show(self.CvTtoolbar)
        else:
            self.panSzr.Hide(self.CvTcanvas)
            self.panSzr.Hide(self.CvTtoolbar)
        
        self.Show(True)
        
    def BuildFrame(self):
        panel = wx.Panel(self, -1)
        self.panSzr = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(self.panSzr)
        
        # Create rate vs time graph
        self.RvTfigure = Figure((6,4))
        self.RvTaxes = self.RvTfigure.add_subplot(111)
        self.RvTcanvas = FigureCanvasWxAgg(panel, -1, self.RvTfigure)
        self.RvTtoolbar = Toolbar(self.RvTcanvas)
        self.RvTtoolbar.Realize()
        
        # Create comp vs accumulated thickness graph
        self.CvTfigure = Figure((6,3))
        self.CvTaxes = self.CvTfigure.add_subplot(111)
        self.CvTcanvas = FigureCanvasWxAgg(panel, -1, self.CvTfigure)
        self.CvTtoolbar = Toolbar(self.CvTcanvas)
        self.CvTtoolbar.Realize()
        
        # Later, we'll make some more sizers for the other graph controls
        
        self.panSzr.AddMany([(self.RvTtoolbar, 0, wx.LEFT|wx.TOP|wx.RIGHT, 5),
                        (self.RvTcanvas, 0, wx.EXPAND|wx.ALIGN_CENTER, 5),
                        (self.CvTtoolbar, 0, wx.LEFT|wx.TOP|wx.RIGHT, 5),
                        (self.CvTcanvas, 0, wx.EXPAND|wx.ALIGN_CENTER, 5)])
                        
        self.panSzr.Fit(self)
        
    def OnExit(self, event):
        self.Close(True)
        
class DRMU_Settings(wx.Frame):
    def __init__(self, parent):
        no_resize = wx.CAPTION|wx.SYSTEM_MENU|wx.CLIP_CHILDREN|\
                    wx.FRAME_NO_TASKBAR|wx.CLOSE_BOX
        wx.Frame.__init__(self, parent, -1, style=no_resize,
                          title=me+" - User Settings")
        self.parent = parent
        self.BuildFrame()
        
        # Read in Sets from parent
        # Init view settings ----------------------------------------
        self.showCurRateChk.SetValue(parent.Sets['showcur'])
        self.showAvgRateChk.SetValue(parent.Sets['showavg'])
        self.showAggRateChk.SetValue(parent.Sets['showagg'])
        self.showThickChk.SetValue(parent.Sets['showthick'])
        self.logZeroChk.SetValue(parent.Sets['logzero'])
        self.zeroStartChk.SetValue(parent.Sets['zerostart'])
        
        # Init deposition settings ----------------------------------
        self.tgtThickTxt.SetValue(str(parent.Sets['tgtthick']))
        self.codepChk.SetValue(parent.Sets['codep'])
        self.mat1nameTxt.SetValue(str(parent.Sets['mat1name']))
        self.mat1rateTxt.SetValue(str(parent.Sets['mat1rate']))
        self.mat2nameTxt.SetValue(str(parent.Sets['mat2name']))
        self.mat2rateTxt.SetValue(str(parent.Sets['mat2rate']))
        self.primMatSpn.SetValue(parent.Sets['primemat']+1)
        self.tgtCompTxt.SetValue(str(parent.Sets['tgtcomp']))
        
        # Init monitoring settings ----------------------------------
        self.sernumSpn.SetValue(parent.Sets['port'])
        self.baudrtTxt.SetValue(str(parent.Sets['baud']))
        self.logtimeTxt.SetValue(str(parent.Sets['logtime']))
        self.readtimeTxt.SetValue(str(parent.Sets['readtime']))
        self.readnumTxt.SetValue(str(parent.Sets['readnum']))
        self.depsampTxt.SetValue(str(parent.Sets['depsamp']))
        depnum = round(parent.Sets['tgtthick']/parent.Sets['depsamp'],0)
        self.depnumTxt.SetValue(str(depnum))
        
        # all done
        self.Show(True)
        
    def BuildFrame(self):
        panel = wx.Panel(self, -1)
        panSzr = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(panSzr)
        
        # Create Notebook pages
        self.panes = wx.Notebook(panel)
        DefaultFont = wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        self.panes.SetFont(DefaultFont)
        
        txt_sz = (50,-1)
        LblFlags = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL
        
        # View/Behaviour settings -----------------------------------
        viewPan = wx.Panel(self.panes)
        viewSzr = wx.BoxSizer(wx.VERTICAL)
        
        self.showCurRateChk = wx.CheckBox(viewPan, -1, "Show current rate")
        self.showAvgRateChk = wx.CheckBox(viewPan, -1, "Show average rate")
        self.showAggRateChk = wx.CheckBox(viewPan, -1, "Show aggregate rate")
        self.showThickChk = wx.CheckBox(viewPan, -1, "Show layer thickness")
        # self.fontSizeLbl = wx.StaticText(viewPanel)
        self.logZeroChk = wx.CheckBox(viewPan, -1, "Log zeroing events")
        self.zeroStartChk = wx.CheckBox(viewPan, -1, "Zero log on start")
        # self.showTgtRateChk = wx.CheckBox(viewPan, -1, "Graph target rate(s)")
        # self.showTgtCompChk = wx.CheckBox(viewPan, -1,
                                          # "Graph target composition (codep)")
        
        viewChkFlags = wx.ALL|wx.ALIGN_TOP|wx.ALIGN_LEFT
        viewSzr.AddMany([(self.showCurRateChk, 0, viewChkFlags, 5),
                         (self.showAvgRateChk, 0, viewChkFlags, 5),
                         (self.showAggRateChk, 0, viewChkFlags, 5),
                         (self.showThickChk, 0, viewChkFlags, 5)])
        viewSzr.AddSpacer(10)
        viewSzr.AddMany([(self.logZeroChk, 0, viewChkFlags, 5),
                         (self.zeroStartChk, 0, viewChkFlags, 5)])
        viewPan.SetSizerAndFit(viewSzr)
        
        # Deposition settings ----------------------------------------
        depPan = wx.Panel(self.panes)
        depSzr = wx.BoxSizer(wx.VERTICAL)
        
        targetThickLbl = wx.StaticText(depPan, -1, "Target Thickness (A):")
        self.tgtThickTxt = wx.TextCtrl(depPan, -1, size=txt_sz)
        targetThickSzr = wx.BoxSizer(wx.HORIZONTAL)
        targetThickSzr.AddMany([(targetThickLbl, 0, LblFlags, 0),
                                (self.tgtThickTxt, 0, wx.LEFT, 5)])
        
        matTabLbl = wx.StaticText(depPan, -1, "Materials")
        matTabHdFont = wx.Font(11, wx.DEFAULT, wx.NORMAL,
                               wx.NORMAL, underline=True)
        matTabLbl.SetFont(matTabHdFont)
        self.codepChk = wx.CheckBox(depPan, -1, "Codeposition")
        MatTabHdSzr = wx.BoxSizer(wx.HORIZONTAL)
        MatTabHdSzr.Add(matTabLbl, 0, LblFlags, 5)
        MatTabHdSzr.AddSpacer(20)
        MatTabHdSzr.Add(self.codepChk, 0, wx.LEFT|wx.TOP, 5)
        
        MTHnumLbl = wx.StaticText(depPan, -1, "#")
        MTHnameLbl = wx.StaticText(depPan, -1, "Name")
        MTHrateLbl = wx.StaticText(depPan, -1, "Rate (A/s)")
        # MTHcorrLbl = wx.StaticText(depPan, -1, "Correction")
        
        mat1numLbl = wx.StaticText(depPan, -1, "1")
        self.mat1nameTxt = wx.TextCtrl(depPan, -1, size=txt_sz)
        self.mat1rateTxt = wx.TextCtrl(depPan, -1, size=txt_sz)
        
        mat2numLbl = wx.StaticText(depPan, -1, "2")
        self.mat2nameTxt = wx.TextCtrl(depPan, -1, size=txt_sz)
        self.mat2rateTxt = wx.TextCtrl(depPan, -1, size=txt_sz)
        
        MatTabFlags = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM
        MatTabSzr = wx.FlexGridSizer(3,3, 3, 3)
        MatTabSzr.AddMany([(MTHnumLbl, 0, MatTabFlags),
                           (MTHnameLbl, 0, MatTabFlags),
                           (MTHrateLbl, 0, MatTabFlags),
                           (mat1numLbl, 0, MatTabFlags),
                           (self.mat1nameTxt, 0, MatTabFlags),
                           (self.mat1rateTxt, 0, MatTabFlags),
                           (mat2numLbl, 0, MatTabFlags),
                           (self.mat2nameTxt, 0, MatTabFlags),
                           (self.mat2rateTxt, 0, MatTabFlags)])
                           
        primMatLbl = wx.StaticText(depPan, -1, "Primary Material")
        self.primMatSpn = wx.SpinCtrl(depPan, -1, size=txt_sz, max=2, min=1)
        primMatSzr = wx.BoxSizer(wx.HORIZONTAL)
        primMatSzr.AddMany([(primMatLbl, 0, LblFlags, 5),
                            (self.primMatSpn, 0, wx.LEFT, 5)])
        
        targetCompLbl = wx.StaticText(depPan, -1, "Target Composition")
        self.tgtCompTxt = wx.TextCtrl(depPan, -1, size=txt_sz)
        self.targetCompUnitsLbl = wx.StaticText(depPan, -1, "%")
        targetCompSzr = wx.BoxSizer(wx.HORIZONTAL)
        targetCompSzr.AddMany([(targetCompLbl, 0, LblFlags, 0),
                               (self.tgtCompTxt, 0, wx.LEFT, 5),
                               (self.targetCompUnitsLbl, 0, LblFlags)])
        
        depSzrFlags = wx.TOP|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL
        depSzr.AddMany([(targetThickSzr, 0, depSzrFlags, 5),
                        (MatTabHdSzr, 0, depSzrFlags, 5),
                        (MatTabSzr, 0, depSzrFlags, 10),
                        (primMatSzr, 0, depSzrFlags, 5),
                        (targetCompSzr, 0, depSzrFlags, 5)])
        depPan.SetSizerAndFit(depSzr)
        
        # Monitoring settings ---------------------------------------
        monPan = wx.Panel(self.panes)
        monSzr = wx.FlexGridSizer(9, 2, 3, 3)
        
        sernumLbl = wx.StaticText(monPan, -1, "Serial port")
        self.sernumSpn = wx.SpinCtrl(monPan, size=txt_sz, max=20)
        baudrtLbl = wx.StaticText(monPan, -1, "Baud rate")
        self.baudrtTxt = wx.TextCtrl(monPan, size=txt_sz)
        
        logtimeLbl = wx.StaticText(monPan, -1, "Rate logging interval (s)")
        self.logtimeTxt = wx.TextCtrl(monPan, -1, size=txt_sz)
        readtimeLbl = wx.StaticText(monPan, -1, "Rate reading interval (s)")
        self.readtimeTxt = wx.TextCtrl(monPan, -1, size=txt_sz)
        readnumLbl = wx.StaticText(monPan, -1, "Rate readings to average")
        self.readnumTxt = wx.TextCtrl(monPan, -1, size=txt_sz)
        
        depsampLbl = wx.StaticText(monPan, -1, "Depth profile interval (A)")
        self.depsampTxt = wx.TextCtrl(monPan, -1, size=txt_sz)
        depnumLbl = wx.StaticText(monPan, -1, "Depth profile samples")
        self.depnumTxt = wx.TextCtrl(monPan, -1, size=txt_sz)
        
        monSzr.AddMany([(sernumLbl, 0, LblFlags, 0),
                        (self.sernumSpn, 0, wx.LEFT|wx.ALIGN_LEFT, 5),
                        (baudrtLbl, 0, LblFlags, 0),
                        (self.baudrtTxt, 0, wx.LEFT|wx.ALIGN_LEFT, 5)])
        monSzr.AddSpacer(10)
        monSzr.AddSpacer(10)
        monSzr.AddMany([(logtimeLbl, 0, LblFlags, 0),
                        (self.logtimeTxt, 0, wx.LEFT|wx.ALIGN_LEFT, 5),
                        (readtimeLbl, 0, LblFlags, 0),
                        (self.readtimeTxt, 0, wx.LEFT|wx.ALIGN_LEFT, 5),
                        (readnumLbl, 0, LblFlags, 0),
                        (self.readnumTxt, 0, wx.LEFT|wx.ALIGN_LEFT, 5)])
        monSzr.AddSpacer(15)
        monSzr.AddSpacer(15)
        monSzr.AddMany([(depsampLbl, 0, LblFlags, 0),
                        (self.depsampTxt, 0, wx.LEFT|wx.ALIGN_LEFT, 5),
                        (depnumLbl, 0, LblFlags, 0),
                        (self.depnumTxt, 0, wx.LEFT|wx.ALIGN_LEFT, 5)])
        monPan.SetSizerAndFit(monSzr)
       
        # Add pages to panes -------------------------------------------
        self.panes.AddPage(viewPan, "View")
        self.panes.AddPage(depPan, "Deposition")
        self.panes.AddPage(monPan, "Monitoring")
        
        # Add buttons at bottom ----------------------------------------
        self.CancelBtn = wx.Button(panel, -1, "Cancel", size=(60,-1))
        self.ApplyBtn = wx.Button(panel, -1, "Apply", size=(60,-1))
        self.OkayBtn = wx.Button(panel, -1, "Okay", size=(60,-1))
        self.ButtonSzr = wx.BoxSizer(wx.HORIZONTAL)
        self.ButtonSzr.AddStretchSpacer(1)
        self.ButtonSzr.AddMany([(self.CancelBtn, 0, wx.ALL, 10),
                                (self.ApplyBtn, 0, wx.ALL, 10),
                                (self.OkayBtn, 0, wx.ALL, 10)])
        self.ButtonSzr.AddStretchSpacer(1)
        
        # Bind button events
        self.CancelBtn.Bind(wx.EVT_BUTTON, self.OnExit)
        self.ApplyBtn.Bind(wx.EVT_BUTTON, self.OnApply)
        self.OkayBtn.Bind(wx.EVT_BUTTON, self.OnOkay)
        # Bind timing check events
        self.logtimeTxt.Bind(wx.EVT_KILL_FOCUS, self.LogTimeUpdate,
                             self.logtimeTxt)
        self.readnumTxt.Bind(wx.EVT_KILL_FOCUS, self.ReadNumUpdate,
                             self.readnumTxt)
        self.readtimeTxt.Bind(wx.EVT_KILL_FOCUS, self.ReadTimeUpdate, 
                              self.readtimeTxt)
        
        panSzr.Add(self.panes, 1, wx.EXPAND)
        panSzr.Add(self.ButtonSzr)
        panSzr.Fit(self)
    
    def LogTimeUpdate(self, event):
        logT = float(self.logtimeTxt.GetValue())
        readT = round(float(self.readtimeTxt.GetValue()),3)
        if readT > logT:
            self.readtimeTxt.SetValue(str(logT))
            self.readnumTxt.SetValue("1")
        else:
            self.readnumTxt.SetValue(str(int(logT/readT)))
        event.Skip()
            
    def ReadNumUpdate(self, event):
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
            
    def ReadTimeUpdate(self, event):
        logT = float(self.logtimeTxt.GetValue())
        readT = round(float(self.readtimeTxt.GetValue()),3)
        if readT > logT:
            self.readtimeTxt.SetValue(str(logT))
            self.readnumTxt.SetValue("1")
        else:
            self.readtimeTxt.SetValue(str(readT))
            self.readnumTxt.SetValue(str(int(logT/readT)))
        event.Skip()
        
    def OnApply(self, event):
        # Do some error checking and pass settings back to parent
        p = self.parent
        # Store view settings ----------------------------------------
        p.Sets['showcur'] = self.showCurRateChk.GetValue()
        p.Sets['showavg'] = self.showAvgRateChk.GetValue()
        p.Sets['showagg'] = self.showAggRateChk.GetValue()
        p.Sets['showthick'] = self.showThickChk.GetValue()
        p.Sets['logzero'] = self.logZeroChk.GetValue()
        p.Sets['zerostart'] = self.zeroStartChk.GetValue()
        
        # Store deposition settings ----------------------------------
        p.Sets['tgtthick'] = round(float(self.tgtThickTxt.GetValue()),1)
        p.Sets['codep'] = self.codepChk.GetValue()
        p.Sets['mat1name'] = self.mat1nameTxt.GetValue()
        p.Sets['mat1rate'] = round(float(self.mat1rateTxt.GetValue()),3)
        p.Sets['mat2name'] = self.mat2nameTxt.GetValue()
        p.Sets['mat2rate'] = round(float(self.mat2rateTxt.GetValue()),3)
        p.Sets['primemat'] = self.primMatSpn.GetValue() - 1
        p.Sets['tgtcomp'] = round(float(self.tgtCompTxt.GetValue()),2)
        
        # Store monitoring settings ----------------------------------
        p.Sets['port'] = self.sernumSpn.GetValue()
        p.Sets['baud'] = int(self.baudrtTxt.GetValue())
        p.Sets['logtime'] = round(float(self.logtimeTxt.GetValue()),2)
        p.Sets['readtime'] = round(float(self.readtimeTxt.GetValue()),2)
        p.Sets['readnum'] = int(self.readnumTxt.GetValue())
        p.Sets['depsamp'] = round(float(self.depsampTxt.GetValue()),1)
        
        p.UpdateView()
    
    def OnOkay(self, event):
        self.OnApply(None)
        self.OnExit(None)
    
    def OnExit(self, event):
        self.Close(True)
        
app = wx.App(False)
frame = DRMU_Frame(None)
app.MainLoop()
