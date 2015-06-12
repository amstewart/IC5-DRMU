"""Front end for Inficon IC/5 interface.
11.Jun.2015, by David M. Stewart"""

import wx, sys
from wx.lib.pubsub import pub
from threading import Thread

import matplotlib
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import Toolbar, FigureCanvasWxAgg
from matplotlib.figure import Figure

from random import gauss
from time import sleep


class BackEndThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.signal = True
        self.start()

    def run(self):
        increment = 1
        self.thic = 0
        while self.signal:
            wx.CallAfter(self.query, increment)
            sleep(1)
            increment += 1

    def query(self, increment):
        self.rate = round(gauss(0.23,0.02),2)
        self.thic += increment*self.rate
        
        pub.sendMessage("ud", time=increment, rate=self.rate, thick=self.thic)

class DRMU_Frame(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self, parent, wx.ID_ANY,
                          title="DRMU - v2015.1.a - GUI Test")
        
        #Create File menu
        filemenu = wx.Menu()
        fileSave = filemenu.Append(wx.ID_ANY, "&Save log",
                                   "Save current data to file")
        fileExit = filemenu.Append(wx.ID_EXIT,"E&xit")
        #Bind File events
        self.Bind(wx.EVT_MENU, self.OnExit, fileExit)
        #Create Connection menu
        conmenu = wx.Menu()
        conOpen = conmenu.Append(wx.ID_ANY, "O&pen",
                                 "Open serial connection")
        conClose = conmenu.Append(wx.ID_ANY, "C&lose",
                                  "Close serial connection")
        #Bind Connection events
        self.Bind(wx.EVT_MENU, self.StartReading, conOpen)
        self.Bind(wx.EVT_MENU, self.StopReading, conClose)
        #Create menu bar
        menuBar = wx.MenuBar()
        menuBar.Append(filemenu,"&File")
        menuBar.Append(conmenu,"&Connection")
        self.SetMenuBar(menuBar)
        
        #Create labels for rate and thickness
        panel = wx.Panel(self, wx.ID_ANY)
        self.rateLbl = wx.StaticText(panel, wx.ID_ANY, "0.0 A/s",
                                     size=(100,100))
        self.thickLbl = wx.StaticText(panel, wx.ID_ANY, "0.000 kA",
                                      size=(100,100))
        #Create plot
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        self.axes.set_xlim(0,20)
        self.axes.set_ylim(0,3)
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        #Sizers
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.rateLbl, 1, wx.ALL|wx.CENTER, 5)
        sizer.Add(self.thickLbl, 1, wx.ALL|wx.CENTER, 5)
        sizer.Add(self.canvas, 1, wx.ALL|wx.CENTER, 5)
        panel.SetSizer(sizer)
        sizer.Fit(self)
        #sizer.Layout()

        self.DataLog = {'t':[],'r':[],'l':[]}
        
        #Done
        self.h, = self.axes.plot([],[])
        pub.subscribe(self.UpdateData, "ud")
        self.Show(True)

    def StartReading(self, event):
        self.BET = BackEndThread()

    def StopReading(self, event):
        self.BET.signal = False

    def UpdateData(self, time, rate, thick):
        self.DataLog['t'].append(time)
        self.DataLog['r'].append(rate)
        self.DataLog['l'].append(thick)
        #print self.DataLog
        #update display
        self.rateLbl.SetLabel(str(rate)+" A/s")
        self.thickLbl.SetLabel(str(thick)+" A")
        self.h.set_xdata(self.DataLog['t'])
        self.h.set_ydata(self.DataLog['r'])
        self.axes.autoscale()
        self.axes.autoscale_view()
        self.canvas.draw()
        

    def OnExit(self,e):
        self.Close(True)

app = wx.App(False)
frame = DRMU_Frame(None)
app.MainLoop()
