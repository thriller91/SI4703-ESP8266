
import time
from machine import Pin, I2C
from ustruct import pack, unpack
#import builtins




class Si4703_Breakout:

    resetPin_id = 13
    sdioPin_id = 4
    sclkPin_id = 5
    LOW = 0
    HIGH = 1
    
    SI4703 = 0x10
    #si4703_registers = bytearray(32)
    readingorder = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    
    #Register names
    DEVICEID = '0'
    CHIPID = '1'
    POWERCFG = '2'
    CHANNEL = '3'
    SYSCONFIG1 = '4'
    SYSCONFIG2 = '5'
    STATUSRSSI = 'A'
    READCHAN = 'B'
    
    #Register 0x02 - POWERCFG
    SMUTE = 15
    DMUTE = 14
    SKMODE = 10
    SEEKUP = 9
    SEEK = 8
    SEEK_DOWN = 0 #Direction used for seeking. Default is down
    SEEK_UP = 1
    
    #Register 0x03 - CHANNEL
    TUNE = 15
    
    #Register 0x04 - SYSCONFIG1
    RDS = 12
    DE = 11
    
    #Register 0x05 - SYSCONFIG2
    SPACE1 = 5
    SPACE0 = 4
    
    #Register 0x0A - STATUSRSSI
    RDSR = 15
    STC = 14
    SFBL = 13
    AFCRL = 12
    RDSS = 11
    STEREO = 8
    

    #To get the Si4703 inito 2-wire mode, SEN needs to be high and SDIO needs to be low after a reset
    #The breakout board has SEN pulled high, but also has SDIO pulled high. Therefore, after a normal power up
    #The Si4703 will be in an unknown state. RST must be controlled
    def __init__(self):

        self.resetPin = Pin(self.resetPin_id, Pin.OUT)
        self.sdioPin = Pin(self.sdioPin_id, Pin.OUT)
        self.sclkPin = Pin(self.sclkPin_id, Pin.OUT)
        
        self.si4703_registers = bytearray(32)

        self.sdioPin.value(self.LOW) #A low SDIO indicates a 2-wire interface
        self.resetPin.value(self.LOW) #Put Si4703 into reset
        time.sleep_ms(1) #Some delays while we allow pins to settle
        self.resetPin.value(self.HIGH) #Bring Si4703 out of reset with SDIO set to low and SEN pulled high with on-board resistor
        time.sleep_ms(1) #Allow Si4703 to come out of reset
        
        self.i2c = I2C(scl=self.sclkPin, sda=self.sdioPin) #Now that the unit is reset and in I2C inteface mode, we need to begin I2C
        self.i2c.init(scl=self.sclkPin, sda=self.sdioPin)
        
        self.readRegisters() #Read the current register set
        
        self.doublebyteWrite('7',int('0x8100')) #Enable the oscillator, from AN230 page 9, rev 0.61 (works)
        self.updateRegisters() #Update
        
        time.sleep_ms(500) #Wait for clock to settle - from AN230 page 9
        
        self.readRegisters()
        self.doublebyteWrite(self.POWERCFG,int(bin(int('0x4001') | (1<<self.SMUTE) ))) #Enable the IC
        
        self.updateRegisters() #Update
        time.sleep_ms(110) #Max powerup time, from datasheet page 13
        
        #syscfg1 = self.si4703_registers_short[int(self.SYSCONFIG1,16)]
        #syscfg1 = int(bin(syscfg1 | (1<<self.DE)))
        #self.doublebyteWrite(self.SYSCONFIG1,syscfg1)
        #syscfg2 = self.si4703_registers_short[int(self.SYSCONFIG2,16)]
        #syscfg2 = int(bin(syscfg2 | (1<<self.SPACE0)))
        #self.doublebyteWrite(self.SYSCONFIG2,syscfg2)
        #self.updateRegisters()
        
        self.setVolume(7)
        



    #Read the entire register control set from 0x00 to 0x0F
    def readRegisters(self):

        #Si4703 begins reading from register upper register of 0x0A and reads to 0x0F, then loops to 0x00.
        msg = self.i2c.readfrom(self.SI4703, 32)
        for counter, value in enumerate(self.readingorder):
            self.si4703_registers[counter] = msg[value]
        #self.si4703_registers_char = unpack('>32B',self.si4703_registers)
        self.si4703_registers_short = unpack('>16H',self.si4703_registers)
        
    
    def updateRegisters(self):
    
        #self.i2c.start()
        #A write command automatically begins with register 0x02 so no need to send a write-to address
        #First we send the 0x02 to 0x07 control registers
        #In general, we should not write to registers 0x08 and 0x09
        ack = self.i2c.writeto(self.SI4703, self.si4703_registers[4:15])
        #self.i2c.stop()
        return ack
        
    def setVolume(self, vol):
        self.readRegisters()
        self.si4703_registers[11] = int(str(vol), 16)
        self.updateRegisters()
        
    
    def clearSEEKTUNE(self):
        self.readRegisters()
        mychan = self.si4703_registers_short[int(self.CHANNEL,16)]
        mychan = int(bin(mychan & ~(1<<self.TUNE)))
        self.doublebyteWrite(self.CHANNEL,mychan)
        pwrcfg = self.si4703_registers_short[int(self.POWERCFG,16)]
        pwrcfg = int(bin(pwrcfg & ~(1<<self.SEEK)))
        self.doublebyteWrite(self.POWERCFG,pwrcfg)
        self.updateRegisters()
    
        
    def setChannel(self, channels):
        newchannel = int((channels-875)/2)
        self.clearSEEKTUNE()
        mychan = self.si4703_registers_short[int(self.CHANNEL,16)]
        mychan = int(hex(mychan & 0xfe00))
        mychan = int(bin(mychan | newchannel))
        mychan = int(bin(mychan | (1<<self.TUNE)))
        self.doublebyteWrite(self.CHANNEL,mychan)
        self.updateRegisters()
        
        time.sleep_ms(500)
        #self.readRegisters()
        
        while int(bin(self.si4703_registers_short[int(self.STATUSRSSI,16)] & (1<<self.STC))) != 0 :
            #print('waiting for Seek/Tune') 
            self.readRegisters()
            #time.sleep(1)
        
        self.readRegisters()
        mychan = self.si4703_registers_short[int(self.CHANNEL,16)]
        mychan = int(bin(mychan & ~(1<<self.TUNE)))
        self.doublebyteWrite(self.CHANNEL,mychan)
        self.updateRegisters()
        
        while int(bin(self.si4703_registers_short[int(self.STATUSRSSI,16)] & (1<<self.STC))) == 0 :
            #print('waiting for Seek/Tune Complete')
            self.readRegisters()
            #time.sleep(1)
    
    def getChannel(self):
        self.readRegisters()
        channel = int(hex(self.si4703_registers_short[int(self.READCHAN,16)] & 0x03ff))
        return 2*channel + 875
        
        
    def getRSSI(self):
        self.readRegisters()
        rssi = int(hex(self.si4703_registers_short[int(self.STATUSRSSI,16)] & 0xff))
        return rssi/255*100
        
        
    def seek(self, dir):
        self.clearSEEKTUNE()
        pwrcfg = self.si4703_registers_short[int(self.POWERCFG,16)]
        pwrcfg = int(bin(pwrcfg | (1<<self.SKMODE)))
        
        if dir == self.SEEK_DOWN:
            pwrcfg = int(bin(pwrcfg & ~(1<<self.SEEKUP)))
        else:
            pwrcfg = int(bin(pwrcfg | (1<<self.SEEKUP)))
        
        pwrcfg = int(bin(pwrcfg | (1<<self.SEEK)))    
        self.doublebyteWrite(self.POWERCFG,pwrcfg)
        self.updateRegisters()
        
        time.sleep_ms(500)
        #self.readRegisters()
        
        while int(bin(self.si4703_registers_short[int(self.STATUSRSSI,16)] & (1<<self.STC))) != 0 :
            print('waiting for Seek/Tune') 
            self.readRegisters()
            time.sleep(1)
        self.readRegisters()
        valueSFBL = int(bin( self.si4703_registers_short[int(self.STATUSRSSI,16)] & (1<<self.SFBL) ))
        pwrcfg = self.si4703_registers_short[int(self.POWERCFG,16)]
        pwrcfg = int(bin(pwrcfg & ~(1<<self.SEEK)))
        self.doublebyteWrite(self.POWERCFG,pwrcfg)
        self.updateRegisters()
        
        while int(bin(self.si4703_registers_short[int(self.STATUSRSSI,16)] & (1<<self.STC))) == 0 :
            print('waiting for Seek/Tune Complete')
            self.readRegisters()
            time.sleep(1)
        
        if valueSFBL == 1:
            return 0
        else:
            self.getChannel()
        
        
    def doublebyteRead(self, regnum):
        upper_byte = 2*int(regnum)
        lower_byte = upper_byte + 1
        
        bytehex = hex((self.si4703_registers[upper_byte])[2:])
        lower_bytehex = int(hex(self.si4703_registers[lower_byte])[2:])
        
        return str(upper_bytehex*100 + lower_bytehex)
       
        
    def doublebyteWrite(self, regnum, dbl):
        upper_byte = 2*int(regnum)
        lower_byte = upper_byte + 1
        
        self.si4703_registers[upper_byte] = int(hex(dbl >> 8)) 
        self.si4703_registers[lower_byte] = int(hex(dbl & 0x00ff))
        
        
    def doublebyte_hextobin(self, dbl):
        a = bin(int(dbl,16))
        return int(a[2:])
        
    def doublebyte_bintohex(self, b):
        return hex(int(b,2))[2:]


































