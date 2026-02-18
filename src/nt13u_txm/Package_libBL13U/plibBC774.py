import numpy as np
import time
import sys
import xmlrpc.client

# Library functions for BL774 control by python

# global (?) parameters
#IP = "http://192.168.131.1:21100"
IP = "http://10.160.131.1:21100"
TimeWait = 0.5
FilePos = "C:/Users/NT13U/dev/nt13u_txm/src/nt13u_txm/BL_Parameters"
GValuePos = "C:/Users/NT13U/dev/nt13u_txm/src/nt13u_txm/Package_libBL13U"

# just a test
def HWfunc():
    print("Hello World")

# Get proxy setting parameter to connect to 774 server
def getIPaddress():
    IPstr = IP
    ret = xmlrpc.client.ServerProxy(IPstr)
    return ret

# Open / Close ABS03AB
def OpenABS03A():
    c = getIPaddress()
    objname = "bl_tc_plc"
    name = "ABS03a"
    ret = c.execute(objname, "open_ABS", dict(name=name))
    return ret

def CloseABS03A():
    c = getIPaddress()
    objname = "bl_tc_plc"
    name = "ABS03a"
    ret = c.execute(objname, "close_ABS", dict(name=name))
    return ret

def OpenABS03B():
    c = getIPaddress()
    objname = "bl_tc_plc"
    name = "ABS03b"
    ret = c.execute(objname, "open_ABS", dict(name=name))
    return ret

def CloseABS03B():
    c = getIPaddress()
    objname = "bl_tc_plc"
    name = "ABS03b"
    ret = c.execute(objname, "close_ABS", dict(name=name))
    return ret

def OpenFM02():
    c = getIPaddress()
    objname = "bl_tc_plc"
    name = "FM2"
    ret = c.execute(objname, "out_monitor", dict(name=name))
    return ret

def CloseFM02():
    c = getIPaddress()
    objname = "bl_tc_plc"
    name = "FM2"
    ret = c.execute(objname, "in_monitor", dict(name=name))
    return ret

# Get status from Beckhoff w.o. working 774
# If "Ch" == 0 : return all axis (list)
# If "Ch" == n (< 64) : return dict. of the Ch's axis
def getBCStatus(Ch):
    MotNameHead = "motor_beckhoff"
    c = getIPaddress()

    if Ch == 0:
        body = """status/"""
        StatusDict = c.execute(MotNameHead, "send_receive", dict(command=body))
        Ret = StatusDict["axis_status"]
    else:
        body = "status/\"axes\":"+str([Ch])
        StatusDict = c.execute(MotNameHead, "send_receive", dict(command=body))
        Ret = StatusDict["axis_status"][0]
#    print(body)

    return Ret

# stop all motors below Beckhoff
def stopBC():
    MotNameHead = "motor_beckhoff"
    c = getIPaddress()
    body = """stop/"""
    c.execute(MotNameHead,"send_receive", dict(command=body))


# Check if target motor is moving?
def isMoving_BC(Ch):
    ChDict = getBCStatus(Ch)
    ChFlag = ChDict["flags"]
    retBool = ChFlag != 1

    return retBool

# Get pulse valuce of motor "Ch", from the list obtained directly from BC as above
def getMPulse_fromRetList(List, Ch):
    ChDict = List[Ch-1]
    RetPulse = ChDict["m_count"]

    return RetPulse

# Get pulse value of motor "Ch"
# Ch: int value (1 to 40 for 13U-Beckhoff)
def getPulse(Ch):
    ChDict = getBCStatus(Ch)
    ChPulse = int(ChDict["m_count"])
    return ChPulse

def getPulse_old(Ch):
    MotNameHead = "motor_beckhoff"
    MotName = f"{MotNameHead}_ch{str(Ch).zfill(2)}"
    #print(MotName)

    c = getIPaddress()
    ChPulse = c.execute(f"{MotName}","get_position")
    if Ch == 12 or 14:
        status = c.execute(f"{MotName}","get_detail_status")
        ChPulse = status["count"]

    return ChPulse

# Get angle value of encoder for M2 ([0]) and G ([1])
def getEncAngle():
    MotNameHead = "motor_beckhoff"
    MotName1 = f"{MotNameHead}_ch{str(12).zfill(2)}"
    MotName2 = f"{MotNameHead}_ch{str(14).zfill(2)}"
    #print(MotName)

    c = getIPaddress()
    status1 = c.execute(f"{MotName1}","get_detail_status")
    #    MotChEnc = status["encoder"]["position"]

    status2 = c.execute(f"{MotName2}","get_detail_status")
    RetAngles = [status1["encoder"]["position"],status2["encoder"]["position"]]

    return RetAngles

# Get position values in mm (deg. for R1)
def getPos_SMCDs():
    ll = [1, 2, 3, 4]
    retlist = [-100, -100, -100, -100]

    for i in ll:
        retlist[i-1] = getPos_SMCD(i)
    
    return retlist

# Get position value  in mm of motor "Ch"
# Ch: int value (1 to 4 for XMCD14)
# 1 / X, 2 / Y, 3 / Z, 4 / Theta (deg. not mm)
def getPos_SMCD(Ch):
    MotNameHead = "smcd14"
    MotName = f"{MotNameHead}_{str(Ch).zfill(2)}"
    #print(MotName)

    c = getIPaddress()
    ChPos = c.execute(f"{MotName}","get_position")
    speed = c.execute(f"{MotName}","get_speed")

    return ChPos

# Check if this move is safe or not
# DestPulse: target position (abs. value)
# Allow to move only if "homing is done" & "correct position is set"
def SafetyCheckSMCD(Ch, DestPulse):
    CheckVal = 0
    NowZ = getPos_SMCD(3)
    NowX = getPos_SMCD(1)
    NowY = getPos_SMCD(2)

    MotNameHead = "smcd14"
    MotName = f"{MotNameHead}_{str(Ch).zfill(2)}"
    c = getIPaddress()
    IsHome = c.execute(f"{MotName}","is_home")

    if Ch == 1:
        CheckVal = (DestPulse < 7) * (DestPulse > -10) * (NowZ >= 54)
        CheckVal += (DestPulse < 2) * (DestPulse > -9) * (NowZ < 54)
    elif Ch == 2:
        CheckVal = (DestPulse < 10) * (DestPulse > -10) * (NowZ >= 54)
        CheckVal += (DestPulse <= 5.1) * (DestPulse >= -3.1) * (NowZ < 54)
    elif Ch == 3:
        CheckVal = (DestPulse < 130) * (DestPulse > 20) * (NowX < 3.5) * (NowX > -10.0) * (NowY < 5.1)* (NowY > -3.1)
    elif Ch == 4:
        CheckVal = (DestPulse < 245) * (DestPulse > 66)
    else:
        CheckVal = 0

    CheckVal *= IsHome
    if CheckVal == 0:
        print("SOMETHING IS WRONG in the SMCD stage!! Ask BL staff.")
        print(DestPulse, NowX, NowY, NowZ)

    return CheckVal
#    print(1==1)
#    print(10*(1==0), 10*(1==1))

# get current speed
def getspeedSMCD(Ch):
    MotNameHead = "smcd14"
    MotName = f"{MotNameHead}_{str(Ch).zfill(2)}"
    c = getIPaddress()

    CurrentSpeed = c.execute(f"{MotName}","get_speed")
    return CurrentSpeed

# set speed
def setspeedSMCD(Ch, speed):
    MotNameHead = "smcd14"
    MotName = f"{MotNameHead}_{str(Ch).zfill(2)}"
    c = getIPaddress()

    Speedpara = {"speed":float(round(speed,5))}
    c.execute(f"{MotName}","set_speed",Speedpara)    

# Move "Ch" channel of SMCD. Absolute move with "mm".
# axis speed is overwritten.
# Ch: int value (1 to 4 for 13U-SMCD)
# Pulse: float value (abs)
# speed: speed (mm/sec.)
# ShowMsg: if == 1, show message at STDOUT
def AbsMoveSMCD(Ch, Pulse, speed, ShowMsg):
    MotNameHead = "smcd14"
    MotName = f"{MotNameHead}_{str(Ch).zfill(2)}"
    
    CheckSafe = SafetyCheckSMCD(Ch, Pulse)
    if CheckSafe == 0:
        sys.exit(99)

    c = getIPaddress()
    OldSpeed = c.execute(f"{MotName}","get_speed")
    OldSpeed = round(OldSpeed,5)

    TargetVal = Pulse#+getPos_SMCD(Ch)
    if ShowMsg == 1:
        print("Absolute Motion.")
        print("Ch:",Ch,"moves from:",getPos_SMCD(Ch),"to",TargetVal, ". Speed:", speed, "(default: ", OldSpeed,").")

    Speedpara = {"speed":float(round(speed,5))}
    c.execute(f"{MotName}","set_speed",Speedpara)

    MovePara = {"position":TargetVal, "unit":"pulse", "absolute":True, "wait":False}
    c.execute(f"{MotName}","move",MovePara)

    while True:
        time.sleep(TimeWait)
        _is_moving_ = c.execute(f"{MotName}","is_moving")
        if _is_moving_ == False:
            break

    if ShowMsg == 1:
        print("Moving Ch",Ch,"is over.")

# Move "Ch" channel of SMCD. Relative move with "mm".
# axis speed is overwritten.
# Ch: int value (1 to 4 for 13U-SMCD)
# Pulse: float value (abs)
# speed: speed (mm/sec.)
# ShowMsg: if == 1, show message at STDOUT
def RelMoveSMCD(Ch, Pulse, speed, ShowMsg):
    MotNameHead = "smcd14"
    MotName = f"{MotNameHead}_{str(Ch).zfill(2)}"
    
    c = getIPaddress()
    OldSpeed = c.execute(f"{MotName}","get_speed")
    OldSpeed = round(OldSpeed,5)

    TargetVal = Pulse+getPos_SMCD(Ch)

    CheckSafe = SafetyCheckSMCD(Ch, TargetVal)
    if CheckSafe == 0:
        sys.exit(99)

    if ShowMsg == 1:
        print("Relative Motion.")
        print("Ch:",Ch,"moves from:",getPos_SMCD(Ch),"to",TargetVal, ". Speed:", speed, "(default: ", OldSpeed,").")

    Speedpara = {"speed":float(round(speed,5))}
    c.execute(f"{MotName}","set_speed",Speedpara)

    MovePara = {"position":Pulse, "unit":"pulse", "absolute":False, "wait":False}
    c.execute(f"{MotName}","move",MovePara)

    while True:
        time.sleep(TimeWait)
        _is_moving_ = c.execute(f"{MotName}","is_moving")
        if _is_moving_ == False:
            break

    if ShowMsg == 1:
        print("Moving Ch",Ch,"is over.")

# Move "Ch" channel. Relavite move with "Pulse".
# Ch: int value (1 to 40 for 13U-Beckhoff)
# Pulse: int value (relative)
# ShowMsg: if == 1, show message at STDOUT
def movePulse(Ch, Pulse, ShowMsg):
    MotNameHead = "motor_beckhoff"
    MotName = f"{MotNameHead}_ch{str(Ch).zfill(2)}"
    
    c = getIPaddress()
    TargetVal = getPulse(Ch)+Pulse
    if ShowMsg == 1:
        print("Ch:",Ch,"moves from:",getPulse(Ch),"to",TargetVal)

    MovePara = {"position":TargetVal, "unit":"pulse", "absolute":True, "wait":False}
    c.execute(f"{MotName}","move",MovePara)

    while True:
        time.sleep(TimeWait)
        _is_moving_ = c.execute(f"{MotName}","is_moving")
        if _is_moving_ == False:
            break

    if ShowMsg == 1:
        print("Moving Ch",Ch,"is over.")

# Move "Ch" channel. Relative move with "Pulse" w.o. using BL774 (774 only pass the string to Beckhoff)
def movePulse_direct(Ch, Pulse, ShowMsg):
    MotName = "motor_beckhoff"
    c = getIPaddress()
    TargetVal = getPulse(Ch)+Pulse
    Wait = 0.1

    if ShowMsg == 1:
        print("Ch:",Ch,"moves from:",getPulse(Ch),"to",TargetVal)

#    body = "move/\"mode\":\"abs\", \"drive\":"+str([{"Ch":int(Ch),"dest":float(TargetVal)}])
    body = "move/\"mode\":\"abs\", \"drive\":[{\"axis\":"+str(int(Ch))+", \"dest\":"+str(float(TargetVal))+"}]"
#    print(body)
    c.execute(MotName, "send_receive", dict(command=body))

    while True:
        time.sleep(Wait)
#        DifPulse = TargetVal - getPulse(Ch)
#        print(getBCStatus(Ch))
        if isMoving_BC(Ch) == False:
           break

    if ShowMsg == 1:
        print("Moving Ch",Ch,"is over.")

# Move "Ch" channel. Relavite move with "Pulse".
# Ch: int value (1 to 40 for 13U-Beckhoff)
# Pulse: int value (relative)
# ShowMsg: if == 1, show message at STDOUT
def movePulse2(Ch1, Pulse1, Ch2, Pulse2, ShowMsg):
    MotNameHead = "motor_beckhoff"
    MotName1 = f"{MotNameHead}_ch{str(Ch1).zfill(2)}"
    MotName2 = f"{MotNameHead}_ch{str(Ch2).zfill(2)}"

    c = getIPaddress()
    TargetVal1 = getPulse(Ch1)+Pulse1
    TargetVal2 = getPulse(Ch2)+Pulse2
    if ShowMsg == 1:
        print("Ch1:",Ch1,"moves from:",getPulse(Ch1),"to",TargetVal1)
        print("Ch2:",Ch2,"moves from:",getPulse(Ch2),"to",TargetVal2)

    MovePara1 = {"position":TargetVal1, "unit":"pulse", "absolute":True, "wait":False}
    MovePara2 = {"position":TargetVal2, "unit":"pulse", "absolute":True, "wait":False}
    c.execute(f"{MotName1}","move",MovePara1)
    c.execute(f"{MotName2}","move",MovePara2)

    while True:
        time.sleep(TimeWait)
        _is_moving_ = c.execute(f"{MotName1}","is_moving")
        _is_moving2_ = c.execute(f"{MotName2}","is_moving")
        if _is_moving_ == False and _is_moving2_ == False:
            break

    if ShowMsg == 1:
        print("Moving is over.")

def movePulse2_direct(Ch1, Pulse1, Ch2, Pulse2, ShowMsg):
    MotName = "motor_beckhoff"
    c = getIPaddress()
    TargetVal1 = getPulse(Ch1)+Pulse1
    TargetVal2 = getPulse(Ch2)+Pulse2
    Wait = 0.1

    if ShowMsg == 1:
        print("Ch1:",Ch1,"moves from:",getPulse(Ch1),"to",TargetVal1)
        print("Ch2:",Ch2,"moves from:",getPulse(Ch2),"to",TargetVal2)

    body = "move/\"mode\":\"abs\", \"drive\":[{\"axis\":"+str(int(Ch1))+", \"dest\":"+str(float(TargetVal1))+"}"
    body += ", {\"axis\":"+str(int(Ch2))+", \"dest\":"+str(float(TargetVal2))+"}]"
#    print(body)
    c.execute(MotName, "send_receive", dict(command=body))

    while True:
        time.sleep(Wait)
#        DifPulse = TargetVal - getPulse(Ch)
#        print(getBCStatus(Ch))
        if isMoving_BC(Ch1) == False and isMoving_BC(Ch2) == False:
           break

    if ShowMsg == 1:
        print("Moving is over.")

def movePulse3(Ch1, Pulse1, Ch2, Pulse2, Ch3, Pulse3, ShowMsg):
    MotNameHead = "motor_beckhoff"
    MotName1 = f"{MotNameHead}_ch{str(Ch1).zfill(2)}"
    MotName2 = f"{MotNameHead}_ch{str(Ch2).zfill(2)}"
    MotName3 = f"{MotNameHead}_ch{str(Ch3).zfill(2)}"

    c = getIPaddress()
    TargetVal1 = getPulse(Ch1)+Pulse1
    TargetVal2 = getPulse(Ch2)+Pulse2
    TargetVal3 = getPulse(Ch3)+Pulse3
    if ShowMsg == 1:
        print("Ch1:",Ch1,"moves from:",getPulse(Ch1),"to",TargetVal1)
        print("Ch2:",Ch2,"moves from:",getPulse(Ch2),"to",TargetVal2)
        print("Ch3:",Ch3,"moves from:",getPulse(Ch3),"to",TargetVal3)

    MovePara1 = {"position":TargetVal1, "unit":"pulse", "absolute":True, "wait":False}
    MovePara2 = {"position":TargetVal2, "unit":"pulse", "absolute":True, "wait":False}
    MovePara3 = {"position":TargetVal3, "unit":"pulse", "absolute":True, "wait":False}
    c.execute(f"{MotName1}","move",MovePara1)
    c.execute(f"{MotName2}","move",MovePara2)
    c.execute(f"{MotName3}","move",MovePara3)

    while True:
        time.sleep(TimeWait)
        _is_moving_ = c.execute(f"{MotName1}","is_moving")
        _is_moving2_ = c.execute(f"{MotName2}","is_moving")
        _is_moving3_ = c.execute(f"{MotName3}","is_moving")
        if _is_moving_ == False and _is_moving2_ == False and _is_moving3_ == False:
            break

    if ShowMsg == 1:
        print("Moving is over.")

def CheckCTused():

    file = GValuePos + "gValues.dat"
    with open(file, mode="r") as f:
        lines = [line.strip() for line in f.readlines()]

    retVal = int(lines[1])
    return retVal

def ChangeCTusedVal(val):

    file = GValuePos + "gValues.dat"
    with open(file, mode="r") as f:
        lines = [line.strip() for line in f.readlines()]

#    print(lines)
    linelist = lines
    linelist[1] = str(int(val))

    with open(file, mode="w") as f:
        for line in lines:
            line += "\r\n"
            f.write(line)

    return val

def CheckM2Gsyncused():

    file = GValuePos + "gValues.dat"
    with open(file, mode="r") as f:
        lines = [line.strip() for line in f.readlines()]

    retVal = int(lines[2])
    return retVal

def ChangeM2GsyncusedVal(val):

    file = GValuePos + "gValues.dat"
    with open(file, mode="r") as f:
        lines = [line.strip() for line in f.readlines()]

#    print(lines)
    linelist = lines
    linelist[2] = str(int(val))

    with open(file, mode="w") as f:
        for line in lines:
            line += "\r\n"
            f.write(line)

    return val

# M2Gsync mode が異常終了した時に備えて、sync mode とかを解除する
def ResetM2GsyncCounter():
    c = getIPaddress()
    m2g_objname = "bl_13u_m2g_sync"
    ct_objname = "ct08-01c"

    M2Gdict = dict(mode=str("off"))
    c.execute(m2g_objname,"set_sync_mode",M2Gdict)
    c.execute(ct_objname,"stop")
    c.execute(ct_objname,"set_count_mode",dict(mode="timer", time=10))
    ChangeCTusedVal(0)
    ChangeM2GsyncusedVal(0)

# Get counter value with dwell time of "dwellTime" at the counter Channel "CtCh"
# dwellTime: int value (msec.)
# CtCh: int calue (0 to 7 for 13U)
def getCT(dwellTime, CtCh):
    c = getIPaddress()
    Cval = c.execute("ct08-01c", "count", {"mode":"timer", "time":dwellTime})["count"][CtCh]

    return Cval

# Get counter values with dwell time of "dwellTime"
# dwellTime: int value (msec.)
def getCTlist(dwellTime):
    c = getIPaddress()
    Cvallist = c.execute("ct08-01c", "count", {"mode":"timer", "time":dwellTime})["count"]

    return Cvallist

# Open the parameter files for M2G and return the list for interpolation
def ReadM2Gpara(FilePos):
#    FilePos = "./BL_Parameters"
#    M2Gpos = FilePos + "/short_recM2G.dat"
    M2Gpos = FilePos + "/recM2G.dat"
    Bpos = FilePos + "/tstB.dat"
    Kpos = FilePos + "/tstK2.dat"

#    print(M2Gpos)
# return list (M2_pulse, M2_enc, G_pulse, G_enc, B_angle, B_En, K_angle, K_en)
    retlist = [[],[],[],[],[],[],[],[]]
    
    with open(M2Gpos) as f:
        for line in f:
            linelist = line.split(",")
            retlist[0].append(float(linelist[0]))
            retlist[1].append(float(linelist[1]))
            retlist[2].append(float(linelist[2]))
            retlist[3].append(float(linelist[3].strip()))

    with open(Bpos) as f:
        for line in f:
            linelist = line.split(",")
            retlist[4].append(float(linelist[0]))
            retlist[5].append(float(linelist[1].strip()))
    
    with open(Kpos) as f:
        for line in f:
            linelist = line.split(",")
            retlist[6].append(float(linelist[0]))
            retlist[7].append(float(linelist[1].strip()))

    return retlist

# calculate energy offset by sigmoid
# Parameter: from B, C, Fe, Co, Cu, Sm, Si, S, Ru (2024Aug. - Nov.)
def calcEofs(En):

    ParaList = [15.746,-115.17,4354.3,2017.3]
    retVal = ParaList[0]+ParaList[1]/(1+np.exp(-(En-ParaList[2])/ParaList[3]))

    return retVal

# Calculate M2 & G values from Energy
def M2Gcalc(setEnergy, offset):

    offsetM2G = 0.132
    #TimeWait = 0.2
    targetVal = setEnergy

    # FilePos = "/home/user13u/PyCodes/BL_Parameters"
    ParaLists = ReadM2Gpara(FilePos)
    
    # interpolate the lists to obtain pulse values to be moved
    NP_M2P = np.array(ParaLists[0])
    NP_M2E = np.array(ParaLists[1])
    NP_GP = np.array(ParaLists[2])
    NP_GE = np.array(ParaLists[3])
    NP_BE = np.array(ParaLists[4])
    NP_B = np.array(ParaLists[5])
    NP_KE = np.array(ParaLists[6])
    NP_K = np.array(ParaLists[7])

    # calculate inoterpolate values: angle(E)
    Kval = np.interp(targetVal, NP_KE, NP_K)
    Bval = np.interp(targetVal, NP_BE, NP_B)

    M2Target = Kval + offset
    GTarget = Bval + offset - offsetM2G

#    print("M2:",M2Target,"G:",GTarget)

    M2Pulse = np.interp(+1*M2Target, -1*NP_M2E, NP_M2P)
    GPulse = np.interp(+1*GTarget, -1*NP_GE, NP_GP)
    M2Pulse = float(int(M2Pulse))
    GPulse = float(int(GPulse))

#    print("M2 pulse:",M2Pulse,"G pulse:",GPulse)
    retlist = [M2Pulse,GPulse]
    return retlist

# M2G energy set to be included in modules
# no wait
def M2Gset_module(setEnergy):

    offsetM2G = 0.132
    offset = 0#.092
    #TimeWait = 0.2
    targetVal = setEnergy

    # FilePos = "/home/user13u/PyCodes/BL_Parameters"
    ParaLists = ReadM2Gpara(FilePos)
    
    # interpolate the lists to obtain pulse values to be moved
    NP_M2P = np.array(ParaLists[0])
    NP_M2E = np.array(ParaLists[1])
    NP_GP = np.array(ParaLists[2])
    NP_GE = np.array(ParaLists[3])
    NP_BE = np.array(ParaLists[4])
    NP_B = np.array(ParaLists[5])
    NP_KE = np.array(ParaLists[6])
    NP_K = np.array(ParaLists[7])

    # calculate inoterpolate values: angle(E)
    Kval = np.interp(targetVal, NP_KE, NP_K)
    Bval = np.interp(targetVal, NP_BE, NP_B)

    M2Target = Kval + offset
    GTarget = Bval + offset - offsetM2G

    M2Pulse = np.interp(+1*M2Target, -1*NP_M2E, NP_M2P)
    GPulse = np.interp(+1*GTarget, -1*NP_GE, NP_GP)
    M2Pulse = float(int(M2Pulse))
    GPulse = float(int(GPulse))
    #print(M2Pulse, GPulse)
    # Go to initial value (+backrush)

    MotNameHead = "motor_beckhoff"
    MotName1 = f"{MotNameHead}_ch{str(12).zfill(2)}"
    MotName2 = f"{MotNameHead}_ch{str(14).zfill(2)}"

    c = getIPaddress()

    MovePara1 = {"position":M2Pulse, "unit":"pulse", "absolute":True, "wait":False}
    MovePara2 = {"position":GPulse, "unit":"pulse", "absolute":True, "wait":False}
    c.execute(f"{MotName1}","move",MovePara1)
    c.execute(f"{MotName2}","move",MovePara2)
#    movePulse2(12, M2Pulse - getPulse(12), 14, GPulse - getPulse(14), 0)

# M2G energy set to be included in modules
# Ch: 0 from M2, 1 from G, 2 from analytical calculation
def M2GgetEnergy_module(Ch):

    Ch = int(Ch)
    offsetM2G = 0.132
    offset = 0#.092
    #TimeWait = 0.2
    targetVal = 1000

    MotPulseList = getBCStatus(0)
    M2Pulse = getMPulse_fromRetList(MotPulseList, 12)
    GPulse = getMPulse_fromRetList(MotPulseList, 14)
#    print("Pulses:",M2Pulse,GPulse)

    # FilePos = "/home/user13u/PyCodes/BL_Parameters"
    ParaLists = ReadM2Gpara(FilePos)
    
    # make numpy arrays.
    # pairs ... (M2Pulse, M2EncAngle), (GPulse, GEncAngle), (BEnergy, BAngle), (KEnergy, KAngle)
    NP_M2Pulse = np.array(ParaLists[0])
    NP_M2EncAngle = np.array(ParaLists[1])
    NP_GPulse = np.array(ParaLists[2])
    NP_GEncAngle = np.array(ParaLists[3])
    NP_BEnergy = np.array(ParaLists[4])
    NP_BAngle = np.array(ParaLists[5])
    NP_KEnergy = np.array(ParaLists[6])
    NP_KAngle = np.array(ParaLists[7])

    # calculate interpolate values: pulses to angles
    M2Angle = np.interp(-1*M2Pulse,-1*NP_M2Pulse,NP_M2EncAngle)
    GAngle = np.interp(-1*GPulse,-1*NP_GPulse,NP_GEncAngle)
#    print("Angles: ",M2Angle, GAngle)
    GAngle -= offsetM2G

    # analytical energy calculation
    AAngle = M2Angle * 2 - GAngle
    RetEn3 = np.cos(np.radians(AAngle))-np.cos(np.radians(GAngle))
    RetEn3 *= (1/600)*1E6
    RetEn3 = 1239.84/RetEn3

    # calculate interpolate values: angles to energy
    RetEn1 = np.interp(+1*M2Angle,-1*NP_KAngle,NP_KEnergy)
    RetEn2 = np.interp(+1*GAngle, -1*NP_BAngle, NP_BEnergy)
#    print("Energy: ",RetEn1, RetEn2, RetEn3)

    RetEnList = [RetEn1,RetEn2,RetEn3]
    RetEnergy = round(RetEnList[Ch],3)

    return RetEnergy

# M2G energy scan to be included in modules
def M2Gswp_module(FileName, SaveFilePos, iVal, dVal, fVal, dwellTime):

#    FileName = str(args[1])
    # Save file name is imported as an argument
#    iVal = 920
#    dVal = 1.0
#    fVal = 1080
#    dwellTime = 500
#    ShowMsgInterval = 20
#    SaveFilePos = "./data/data20240926/"
    #FileName = "Itest.dat"

    offsetM2G = 0.132
    offset = 0#.092
    #TimeWait = 0.2
    targetVal = iVal
    TotalLines = round(abs((fVal - iVal)/dVal)+1)

# Make File Header
    FileName = SaveFilePos + FileName
    with open(FileName, mode="a") as f:
        WriteStr = "# Initial Energy: " + str(iVal)+ "\r\n"
        f.write(WriteStr)
        WriteStr = "# Final Energy: " + str(fVal)+ "\r\n"
        f.write(WriteStr)
        WriteStr = "# dwell Time (ms): " + str(dwellTime)+ "\r\n"
        f.write(WriteStr)
        WriteStr = "# E (eV), counts (ch. 0 to 7)"+ "\r\n"
        f.write(WriteStr)
        WriteStr = "\r\n"
        f.write(WriteStr)

    # FilePos = "/home/user13u/PyCodes/BL_Parameters"
    ParaLists = ReadM2Gpara(FilePos)
    
    # interpolate the lists to obtain pulse values to be moved
    NP_M2P = np.array(ParaLists[0])
    NP_M2E = np.array(ParaLists[1])
    NP_GP = np.array(ParaLists[2])
    NP_GE = np.array(ParaLists[3])
    NP_BE = np.array(ParaLists[4])
    NP_B = np.array(ParaLists[5])
    NP_KE = np.array(ParaLists[6])
    NP_K = np.array(ParaLists[7])

    # calculate inoterpolate values: angle(E)
    Kval = np.interp(targetVal, NP_KE, NP_K)
    Bval = np.interp(targetVal, NP_BE, NP_B)

    M2Target = Kval + offset + 0.1
    GTarget = Bval + offset - offsetM2G + 0.1

    M2Pulse = np.interp(+1*M2Target, -1*NP_M2E, NP_M2P)
    GPulse = np.interp(+1*GTarget, -1*NP_GE, NP_GP)
    M2Pulse = float(int(M2Pulse))
    GPulse = float(int(GPulse))
    #print(M2Pulse, GPulse)

    # Go to initial value (+backrush)
    movePulse2(12, M2Pulse - getPulse(12), 14, GPulse - getPulse(14), 0)
    targetVal = iVal

    ii = 0
#    print("Start measurement:")

    while True:
        if targetVal > fVal + dVal*0.5:
            break

        ii += 1
        Kval = np.interp(targetVal, NP_KE, NP_K)
        Bval = np.interp(targetVal, NP_BE, NP_B)
        M2Target = Kval + offset
        GTarget = Bval + offset - offsetM2G

        M2Pulse = np.interp(+1*M2Target, -1*NP_M2E, NP_M2P)
        GPulse = np.interp(+1*GTarget, -1*NP_GE, NP_GP)
        M2Pulse = float(int(M2Pulse))
        GPulse = float(int(GPulse))

        movePulse2(12, M2Pulse - getPulse(12), 14, GPulse - getPulse(14), 0)

        Cvals = getCTlist(dwellTime)
        WriteStr = str(round(targetVal, 5))+", "
        WriteStr += str(Cvals[0]) +", " + str(Cvals[1]) +", " + str(Cvals[2]) + ", " +str(Cvals[3])+", " 
        WriteStr += str(Cvals[4])+", "  + str(Cvals[5])+", "  + str(Cvals[6])+", " + str(Cvals[7]) + "\r\n"
        with open(FileName, mode="a") as f:
            f.write(WriteStr)

        targetVal += dVal

# Read BL parameters
def ReadMGS():
    RetStr = "# Beamline parameters \r\n"

    c = getIPaddress()

# Read mirrors
    RetStr += "# Mirrors: \r\n"

    CurrentPNameList = ["Something Wrong!!"]*5
    CPosList = [float("nan")]*5
    ThresholdList = [60000, 3500, 31500, -150000, 10000]

    # Read M1 pos.
    CPosList[0] = getPulse(8)
    if CPosList[0] < -ThresholdList[0]:
        CurrentPNameList[0] = "M1: Pd (0)"
    elif CPosList[0] > +ThresholdList[0]:
        CurrentPNameList[0] = "M1: Si (2)"
    else:
        CurrentPNameList[0] = "M1: Au (1)"

    # Read M2 pos.
    CPosList[1] = getPulse(11)
    if CPosList[1] < -ThresholdList[1]:
        CurrentPNameList[1] = "M2: Au (0)"
    elif CPosList[1] > +ThresholdList[1]:
        CurrentPNameList[1] = "M2: Pd (2)"
    else:
        CurrentPNameList[1] = "M2: Si (1)"

    # Read G pos.
    CPosList[2] = getPulse(13)
    if CPosList[2] < ThresholdList[2]-500:
        CurrentPNameList[2] = "G: Pd-10nm (0)"
    elif CPosList[2] > ThresholdList[2]+500:
        CurrentPNameList[2] = "G: Au-10nm (2)"
    else:
        CurrentPNameList[2] = "G: Pd-20nm (1)"

    # Read M3AB pos.
    CPosList[3] = getPulse(23)
    if CPosList[3] < ThresholdList[3]:
        CurrentPNameList[3] = "M3: B,"
    else:
        CurrentPNameList[3] = "M3: A,"

    # Read M3Y pos.
    CPosList[4] = getPulse(25)
    if CPosList[4] < -ThresholdList[4]:
        CurrentPNameList[4] = "Si (0)"
    else:
        CurrentPNameList[4] = "Pd (1)"

    RetStr += "# "+str(CurrentPNameList) + "\r\n"

    # Read S2
    RetStr += "# S2 (h, v) in um \r\n"
    RetStr += "# ( "+str(round(getPulse(19)/20))+", "+str(round(getPulse(21)/20))+" )\r\n"
    
    return RetStr

# Calculate M1-X1 (Ch6) and X2 (Ch7) values to align the beam to the center of S2
def calcM1corr(En):
    X1 = 19448+2274.7*pow(En,-0.68533)
    X2 = 19189-2274.7*pow(En,-0.68533)

    retList = [int(round(X1)),int(round(X2))]
    return retList

# Move M1-X1&X2 for correction
def setM1corr():
    Energy = M2GgetEnergy_module(0)
    X1toGo = calcM1corr(Energy)[0]
    X2toGo = calcM1corr(Energy)[1]
#    movePulse2(6, -100, 7, 100, 0)

    X1now = getPulse(6)
    X2now = getPulse(7)

#    print(X1toGo, X2toGo)
    difX1 = X1toGo - X1now
    difX2 = X2toGo - X2now

    movePulse2(6, difX1, 7, difX2, 0)
#    print(getPulse(6),getPulse(7))
