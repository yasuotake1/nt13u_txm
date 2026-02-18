import numpy as np
import time
import sys
import xmlrpc.client
import math

# Library functions for BL774 control by python

# global (?) parameters
#IP = "http://192.168.131.1:21100"
IP = "http://10.160.131.1:21100"
TimeWait = 0.5
FilePos = "C:/Users/NT13U/dev/nt13u_txm/src/meas/BL_Parameters/"
GValuePos = "C:/Users/NT13U/dev/nt13u_txm/src/meas/Package_libBL13U/"

# Get proxy setting parameter to connect to 774 server
def getIPaddress():
    IPstr = IP
    ret = xmlrpc.client.ServerProxy(IPstr)
    return ret

# get ring current
def GetRingCurrent():
    c = getIPaddress()
    objname = "sr_mdaq"
    cur = c.execute(objname,"get_ringcurrent")

    return cur

def CheckPSused():

    file = GValuePos + "gValues.dat"
    with open(file, mode="r") as f:
        lines = [line.strip() for line in f.readlines()]

    retVal = int(lines[2])
    return retVal

def ChangePSusedVal(val):

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

# Get current value of ID_PS "Ch"
# Ch: int value (1 to 3 for ID13U-PS)
def getPSval(Ch):
    PSNameHead = "sr_id_13_ps"
    PSName = f"{PSNameHead}_{str(Ch).zfill(1)}"
    #print(PSName)

    c = getIPaddress()
#    PSCurrent = c.execute(f"{PSName}","get_status")
    PSCurrent = c.execute(f"{PSName}","get_current")

    return PSCurrent

# Set pulse value of ID_PS "Ch"
# Ch: int value (1 to 3 for ID13U-PS)
# Current: target current value (0 to 20 A)
def setPSval(Ch, Current, step):
    PSNameHead = "sr_id_13_ps"
    PSName = f"{PSNameHead}_{str(Ch).zfill(1)}"
    #print(PSName)

    setPara = {"current":float(Current), "step":step}
    c = getIPaddress()
    retVal = c.execute(f"{PSName}","set_current", setPara)

    return retVal

####
# fire_and_forget 使って一気に目指すphi2に行くコードを書きましょ。
####
# Set all PS values to zero.
def setPSzero():
    PSNameHead = "sr_id_13_ps"
    setPara = {"current":float(0), "step":0.5}
    c = getIPaddress()

    PSName1 = f"{PSNameHead}_{str(1).zfill(1)}"
    PSName2 = f"{PSNameHead}_{str(2).zfill(1)}"
    PSName3 = f"{PSNameHead}_{str(3).zfill(1)}"
    c.fire_and_forget(f"{PSName1}","set_current", setPara)
    c.fire_and_forget(f"{PSName2}","set_current", setPara)
    c.fire_and_forget(f"{PSName3}","set_current", setPara)

    while True:
        time.sleep(0.5)
        if abs(getPSval(1)) < 0.01 and abs(getPSval(2)) < 0.01 and abs(getPSval(3)) < 0.01:
            break

#    setPSval(1,0,0.5)
#    setPSval(2,0,0.5)
#    setPSval(3,0,0.5)
    return 1

# return True if all PS values = 0
def checkPSzero():
    c1 = abs(getPSval(1)) < 0.005
    c2 = abs(getPSval(2)) < 0.005
    c3 = abs(getPSval(3)) < 0.005
    check = c1 and c2 and c3

    return check

# Get gap value of ID "Ch"
# Ch: int value (1 to 4 for ID13U)
def getIDval(Ch):
    IDNameHead = "sr_id_13"
    IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"
#    print(IDName)

    c = getIPaddress()
    IDgap = c.execute(f"{IDName}","get_status")["position"]

    return IDgap

# check if ID is moving
# 0 for fixed, 1 is moving
def ismoving_ID(Ch):
    IDNameHead = "sr_id_13"
    IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"
    c = getIPaddress()
    ret = c.execute(f"{IDName}","is_moving")

    return ret

# Set gap value of ID "Ch"
# Ch: int value (1 to 4 for ID13U)
# targetGap: target gap value (15 to 220 mm)
def setIDval(Ch, targetGap):
    IDNameHead = "sr_id_13"
    IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"
#    print(IDName)

    setgapPara = {"gap":float(targetGap)}
    c = getIPaddress()
    IDgap = c.execute(f"{IDName}","set_gap", setgapPara)

    while True:
        time.sleep(2.0)
        _is_moving_ = c.execute(f"{IDName}","is_moving")
        if _is_moving_ == False:
            break

#    print("Moving Ch",Ch,"is over.")
#    return IDgap

# Set phase of ID "Ch
# Ch: int value (1 to 4)
# targetPhase: target phase value (mm)
def setIDphase(Ch, targetPhase):
    IDNameHead = "sr_id_13"
    IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"
    setPhasePara = {"phase":float(targetPhase), "absolute":True}

    c = getIPaddress()
    c.fire_and_forget(f"{IDName}","set_phase", setPhasePara)
    

# Return ID + FE parameters
def ReadIDFE():

    RetStr = "# ID & FE parameters \r\n"
    c = getIPaddress()

    RetStr += "# ID (gap, phase) in mm \r\n"
# Read ID parameters
    IDNameHead = "sr_id_13"
    for i in range(4):
        Ch = int(i+1)
        IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"
        IDgap = c.execute(f"{IDName}","get_gap")
        IDphase = c.execute(f"{IDName}","get_phase")
        IDstr = "# ID " + str(Ch) + ": ( "+str(IDgap)+", "+str(IDphase)+" )\r\n"
        RetStr += IDstr
        #print(IDstr)

# Read FE parameter
    SlitName = "bl_fe_13u_xyslit_1"
    PosSlit = c.execute(SlitName,'get_position')
    FES_height = float(np.round(PosSlit["height"], 2))
    FES_width = float(np.round(PosSlit["width"], 2))

    RetStr += "# FE aperture (width, height) in mm \r\n"
    RetStr += "# ( " + str(FES_width) + ", "+str(FES_height) + " )\r\n"

    return RetStr

# Return ID modes
# 0 : VHVH, 1: LRLR-17.1 mm, 2: LRLR-19.21 mm, -1: else (error!)
def CheckIDmode():
    retVal = 0
    checkVal = 0
    c = getIPaddress()
    CheckList = [+28.00*0.5, -17.10, -19.21]
    PhaseList = [0,0,0]
    IndxList = [-1]*4

# Read ID parameters
    IDNameHead = "sr_id_13"
    for i in range(4):
        Ch = int(i+1)
        IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"
        IDphase = c.execute(f"{IDName}","get_phase")
        IDphaseV = float(0.5*(IDphase["upper"] + IDphase["lower"]))

        for j in range(3):
            PhaseList[j] = abs(CheckList[j]*((-1)**(Ch % 2))*1 + (IDphaseV-14*(j==0))*1)

        IndxList[i] = PhaseList.index(min(PhaseList))
        checkVal += (min(PhaseList) < 0.01)
#        print(PhaseList, checkVal)

#    print(IndxList)
    if min(IndxList) == max(IndxList) and checkVal == 4 :
        retVal = min(IndxList)
    else:
        retVal = -1

    return retVal

# calculate gap value from energy for arbitral ID modes
# Beammode: 0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV)
def calcIDgap(Ch, targetEn, Beammode):
    ofsL = [[30.4233,42.5778,30.2407,42.4518],[29.7687,41.5748,29.4442,41.4544],[35.8813,35.7906,35.7026,35.6792],[34.3515,34.1273,33.9191,34.0288]]
    I0L = [[6.9808,8.7169,7.1318,8.6431],[6.4893,8.2213,6.3399,8.1708],[8.23364,8.19594,8.22859,8.12492],[7.71785,7.88847,8.11036,7.99655]]
    cfL = [[3046.18,2940.92,3070.33,2901.61],[8571.62,8361.06,8384.97,8306.67],[3040.95,3034.96,3039.26,3014.45],[2991.58,3023.15,3068.01,3035.82]]
    e0L = [[-40.4932,13.8063,-57.9024,18.0811],[-30.6169,86.4357,-5.981,91.6275],[-25.3105,-23.2088,-26.6025,-18.8888],[-13.598,-30.9349,-54.6686,-40.7543]]

    ofs = ofsL[Beammode][Ch-1]
    I0 = I0L[Beammode][Ch-1]
    cf = cfL[Beammode][Ch-1]
    e0 = e0L[Beammode][Ch-1]

    if (cf/(targetEn - e0)) > 2:
        retVal = max((ofs - I0*math.log((cf/(targetEn - e0))-2)),15.0)
        #    w[0] - w[1]*ln((w[2]/(x-w[3]))-2)
    else:
        retVal = 80#100

    retVal = round(retVal, 2)
    return retVal

# calculate energy from gap
# Beammode: 0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV)
def calcIDen(Ch, gap, Beammode):
    Energy = 0
    c0L = [[-40.4932,13.8063,-57.9024,18.0811],[-30.617,86.4357,-5.98103,91.6274],[-25.3105,-23.2088,-26.6025,-18.8888],[-13.598,-30.9349,-54.6686,-40.7543]]
    c1L = [[1523.09,1470.46,1535.16,1450.81],[4285.81,4180.53,4192.49,4153.34],[1520.47,1517.48,1519.63,1507.23],[1495.79,1511.57,1534.005,1517.93]]
    c2L = [[25.5846,36.5357,25.2973,36.4609],[25.2707,35.8762,25.0497,35.7908],[30.1742,30.1096,29.999,30.0477],[29.0019,28.6594,28.2974,28.486]]
    c3L = [[6.9808,8.7169,7.1318,8.6431],[6.4893,8.2213,6.3399,8.1708],[8.2336,8.1959,8.2286,8.1249],[7.71785,7.88847,8.11036,7.99655]]

    if gap >= 79.9:
        Energy = -1
    else:
        Energy = c0L[Beammode][Ch-1] + c1L[Beammode][Ch-1] / (1+math.exp(-(gap - c2L[Beammode][Ch-1])/c3L[Beammode][Ch-1]))
        Energy = round(Energy,2)

    return Energy

# set single ID gap from energy with arbitral modes
# wait: false
# Beammode: 0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV)
def setIDgapSingle(Ch,targetEn, Beammode):
    IDNameHead = "sr_id_13"
    IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"

    c = getIPaddress()
    CheckSafe = CheckIDmode()
    if CheckSafe == -1:
        print("ID phase mode is wrong! No gap moved.")   
        sys.exit(99)
# 「論外」の場合以外は単に間違ったgapで測定するだけで光学系その他に害は無いので、エラーチェックは行わない。
    if Beammode == 1:
        targetEn = min(targetEn,3100)
        targetEn = max(targetEn,750)
    else:
        targetEn = min(targetEn,1400)
        targetEn = max(targetEn,180)

    gapVal = max(15,float(calcIDgap(Ch,targetEn,Beammode)))
    setgapPara = {"gap":gapVal, "wait":False}
    IDgap = c.execute(f"{IDName}","set_gap", setgapPara)

    return IDgap

# mode変更用
# 偏光に関わらず、どの場合でも80 mm にはして良いのでmodeチェック等省略
# PSはまず全て0にする
def setIDgapsAll80():

    setPSzero()

    IDNameHead = "sr_id_13"
    IDName1 = f"{IDNameHead}_{str(1).zfill(1)}"
    IDName2 = f"{IDNameHead}_{str(2).zfill(1)}"
    IDName3 = f"{IDNameHead}_{str(3).zfill(1)}"
    IDName4 = f"{IDNameHead}_{str(4).zfill(1)}"

    setgapPara = {"gap":float(80), "wait":False}
    c = getIPaddress()

    c.execute(f"{IDName1}","set_gap", setgapPara)
    c.execute(f"{IDName2}","set_gap", setgapPara)
    c.execute(f"{IDName3}","set_gap", setgapPara)
    c.execute(f"{IDName4}","set_gap", setgapPara)

    while True:
        time.sleep(2.0)
        _is_moving_ = c.execute(f"{IDName3}","is_moving") or c.execute(f"{IDName4}","is_moving") or c.execute(f"{IDName1}","is_moving") or c.execute(f"{IDName2}","is_moving")
        if _is_moving_ == False:
            break

# ID gap full open (220 mm)
# no wait
def setIDgfo(IDch):
    if checkPSzero():
        pass
    else:
        setPSzero()

    IDNameHead = "sr_id_13"
    IDName1 = f"{IDNameHead}_{str(IDch).zfill(1)}"
    setgapPara = {"gap":float(220), "wait":False}
    c = getIPaddress()
    c.execute(f"{IDName1}","set_gap", setgapPara)

# IDmode変更用
# gap all 80 mm -> phase変更
# IDmode: 0: VHVH, 1: LRLR (17.1 mm), 2: LRLR (19.21 mm)
def SetIDmode(IDmode):
    setIDgapsAll80()

    if IDmode == 0:
        setIDphase(1,28.0)
        setIDphase(2,0.0)
        setIDphase(3,28.0)
        setIDphase(4,0.0)
    elif IDmode == 1:
        setIDphase(1,-17.10)
        setIDphase(2,+17.10)
        setIDphase(3,-17.10)
        setIDphase(4,+17.10)
    elif IDmode == 2:
        setIDphase(1,-19.21)
        setIDphase(2,+19.21)
        setIDphase(3,-19.21)
        setIDphase(4,+19.21)
    else:
        pass

    while True:
        time.sleep(2.0)
        val = CheckIDmode()
        if val != -1:
            break

    return val

# calculate PS current (any mode)
# wait: false
# Beammode: 0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV)
# nth を自動検索するかどうか要検討。180-3000 でオールマイティに使える値は無い。現状は電流値で探してみている。
def calcPS(phi2, PSC, En, Itarget, Beammode):

    if Beammode == 0:
        C3slpList = [0.00733004,0.0072901,0.00733645]
        C3ofsList = [-0.0265696,-0.0218741,-0.0299985]
        C4slpList = [-2.334,-2.32655,-2.332585]
        C4ofsList = [428.953,424.911,420.734]
        C4cfList = [0.0,0.0,0.0,0.0]
    elif Beammode == 1:
        C3slpList = [0.00739327,0.00730657,0.00743984]
        C3ofsList = [-0.134749,-0.0660307,-0.125554]
        C4slpList = [0.43298,0.413311,0.386445]
        C4ofsList = [-288.14,-277.466,-260.41]
        C4cfList = [3.8889e-5,4.5637e-5,5.27254e-5]
    elif Beammode == 2:
        C3slpList = [0.0073892,0.0073166,0.0073441]
        C3ofsList = [-0.0052171,-0.045197,-0.0041411]
        C4slpList = [-2.3796,-2.3714,-2.3794]
        C4ofsList = [445.18,444.51,443.36]
        C4cfList = [0.0,0.0,0.0,0.0]
    elif Beammode == 3:
        C3slpList = [0.0074056,0.0073052,0.0073297]
        C3ofsList = [-0.0079495,-0.050884,-0.0039999]
        C4slpList = [-2.3931,-2.3766,-2.3678]
        C4ofsList = [452.13,445.72,431.04]
        C4cfList = [0.0,0.0,0.0,0.0]
    else:
        print("Beammode is wrong...0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV ")
        sys.exit(99)

    nth = 0
    I1 = -1

    while I1 < Itarget:
        phi0 = nth * 180
        I1 = phi0 + (C4ofsList[0] + C4slpList[0]*En + C4cfList[0]*En*En)
        I1 = max([0,I1])
        I1 = np.sqrt(I1/(C3ofsList[0] + C3slpList[0]*En))

        nth += 1

    if I1 > 20:
        nth -= 1

    phi0 = 180 * (nth-2)
    phi2 += 0
    I1l = [0.0,0.0,0.0]
    I2l = [0.0,0.0,0.0]
    I3l = [0.0,0.0,0.0]
    I1l[0] = round(np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[0] + C4slpList[0]*En+ C4cfList[0]*En*En))])/(C3ofsList[0] + C3slpList[0]*En)),3)
    I3l[0] = round(np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[2] + C4slpList[2]*En+ C4cfList[2]*En*En))])/(C3ofsList[2] + C3slpList[2]*En)),3)
    I2l[0] = round(np.sqrt(phi2/(C3ofsList[1] + C3slpList[1]*En)),3)

    phi0 = 180 * (nth-1)
    I1l[1] = round(np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[0] + C4slpList[0]*En+ C4cfList[0]*En*En))])/(C3ofsList[0] + C3slpList[0]*En)),3)
    I3l[1] = round(np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[2] + C4slpList[2]*En+ C4cfList[2]*En*En))])/(C3ofsList[2] + C3slpList[2]*En)),3)
    I2l[1] = round(np.sqrt(phi2/(C3ofsList[1] + C3slpList[1]*En)),3)

    phi0 = 180 * (nth)
    I1l[2] = round(np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[0] + C4slpList[0]*En+ C4cfList[0]*En*En))])/(C3ofsList[0] + C3slpList[0]*En)),3)
    I3l[2] = round(np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[2] + C4slpList[2]*En+ C4cfList[2]*En*En))])/(C3ofsList[2] + C3slpList[2]*En)),3)
    I2l[2] = round(np.sqrt(phi2/(C3ofsList[1] + C3slpList[1]*En)),3)


    if PSC == 1:
        retList = I1l
    elif PSC == 3:
        retList = I3l
    else:
        retList = I2l

    return retList

# calculate phi2 values (any mode)
# ELLI-chi 45 deg. で強くなる条件。つまり、
# LR-mode: LVを0 deg. とする定義で135 deg. 直線偏光
# VH-mode: ここ±45 deg. が左右円
# Beammode: 0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV)
# lin-3rdだけ明らかに値が違うのが気にはなる。これで良いのかどうか、もう少し詳しく調べてみたい
def calcPhi2(En, Beammode):
    RetPhi = 360.0

    if Beammode == 0:
        CList = [909.04,-0.62881,1.0825]
    elif Beammode == 3:
        CList = [831.03,-0.58125,1.0881]
    elif Beammode == 1:
        CList = [-1948.5,1.9093,0.99366]
#        CList = [722.39,-0.051053,1.3029]
    elif Beammode == 2:
        CList = [850.379,-0.68510,1.0651]
    else:
        CList = [360.00,0.00, 1.00]

    RetPhi = CList[0] + CList[1]*pow(En,CList[2])
    tVal = (RetPhi - 180) // 360
    RetPhi -= tVal * 360

    return RetPhi

# set all gaps
# Beammode: 0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV)
def setIDgapsAll(targetEn, Beammode):
    IDNameHead = "sr_id_13"
    IDName1 = f"{IDNameHead}_{str(1).zfill(1)}"
    IDName2 = f"{IDNameHead}_{str(2).zfill(1)}"
    IDName3 = f"{IDNameHead}_{str(3).zfill(1)}"
    IDName4 = f"{IDNameHead}_{str(4).zfill(1)}"
#    print(IDName)
    setgapParaL = [{"gap":float(80.0), "wait":False}]*4

    for i in range(4):
        setgapParaL[i] = {"gap":float(calcIDgap((i+1),targetEn,Beammode)), "wait":False}
#        print(i, calcIDgap((i+1),targetEn,Beammode))
#    c.fire_and_forget(f"{IDName}","set_phase", setPhasePara)

    c = getIPaddress()
    ReadBM = CheckIDmode()
    # 0 : VHVH, 1: LRLR-17.1 mm, 2: LRLR-19.21 mm, -1: else (error!)
    CheckLogic = (Beammode == 0 and ReadBM == 0) or (Beammode == 1 and ReadBM == 0) or (Beammode == 2 and ReadBM == 1)
    CheckLogic = CheckLogic or (Beammode == 3 and ReadBM == 2)
    if CheckLogic:
#        print(setgapParaL[0],setgapParaL[1],setgapParaL[2],setgapParaL[3])
        c.execute(f"{IDName1}","set_gap", setgapParaL[0])
        c.execute(f"{IDName2}","set_gap", setgapParaL[1])
        c.execute(f"{IDName3}","set_gap", setgapParaL[2])
        c.execute(f"{IDName4}","set_gap", setgapParaL[3])

        while True:
            time.sleep(2.0)
            _is_moving_1 = c.execute(f"{IDName1}","is_moving")
            _is_moving_2 = c.execute(f"{IDName2}","is_moving")
            _is_moving_3 = c.execute(f"{IDName3}","is_moving")
            _is_moving_4 = c.execute(f"{IDName4}","is_moving")
            if _is_moving_1 == False and _is_moving_2 == False and _is_moving_3 == False and _is_moving_4 == False:
                break
    else:
        print("Something in ID mode is wrong! No gap moved.")

# fire_and_forget 使って一気に目指すphi2に行く
# Set all PS values to target phi2.
# Itarget : current in A. 0-20 A だが、低めだと微妙なことがあるので10-15 A 推奨
def setPSphi2(phi2, Energy, Itarget, Beammode):

    stepPS = 0.3

    N1 = calcNforPS(phi2, Energy, 1, Itarget, Beammode)
    N2 = calcNforPS(phi2, Energy, 2, Itarget, Beammode)
    PSval1 = calcPS_N(phi2, Energy, N1, Beammode)[0]
    PSval3 = calcPS_N(phi2, Energy, N1, Beammode)[2]
    PSval2 = calcPS_N(phi2, Energy, N2, Beammode)[1]

#    print(N1, N2, PSval1, PSval2, PSval3)

    c = getIPaddress()
    PSNameHead = "sr_id_13_ps"
    setPara1 = {"current":float(PSval1), "step":float(stepPS)}
    setPara2 = {"current":float(PSval2), "step":float(stepPS)}
    setPara3 = {"current":float(PSval3), "step":float(stepPS)}
    PSName1 = f"{PSNameHead}_{str(1).zfill(1)}"
    PSName2 = f"{PSNameHead}_{str(2).zfill(1)}"
    PSName3 = f"{PSNameHead}_{str(3).zfill(1)}"

    c.fire_and_forget(f"{PSName1}","set_current", setPara1)
    c.fire_and_forget(f"{PSName2}","set_current", setPara2)
    c.fire_and_forget(f"{PSName3}","set_current", setPara3)

    while True:
        time.sleep(0.5)
        dist1 = abs(getPSval(1) - PSval1)*1
        dist2 = abs(getPSval(2) - PSval2)*1
        dist3 = abs(getPSval(3) - PSval3)*1

        if dist1 < 0.01 and dist2 < 0.01 and dist3 < 0.01:
            break

    return [N1,N2]

# set PS currents at phi2 from N
def setPSphi2fromN(phi2, Energy, N1, N2, Beammode):

    stepPS = 0.3

    PSval1 = calcPS_N(phi2, Energy, N1, Beammode)[0]
    PSval3 = calcPS_N(phi2, Energy, N1, Beammode)[2]
    PSval2 = calcPS_N(phi2, Energy, N2, Beammode)[1]

#    print(N1, N2, PSval1, PSval2, PSval3)

    c = getIPaddress()
    PSNameHead = "sr_id_13_ps"
    setPara1 = {"current":float(PSval1), "step":float(stepPS)}
    setPara2 = {"current":float(PSval2), "step":float(stepPS)}
    setPara3 = {"current":float(PSval3), "step":float(stepPS)}
    PSName1 = f"{PSNameHead}_{str(1).zfill(1)}"
    PSName2 = f"{PSNameHead}_{str(2).zfill(1)}"
    PSName3 = f"{PSNameHead}_{str(3).zfill(1)}"

    c.fire_and_forget(f"{PSName1}","set_current", setPara1)
    c.fire_and_forget(f"{PSName2}","set_current", setPara2)
    c.fire_and_forget(f"{PSName3}","set_current", setPara3)

    while True:
        time.sleep(0.5)
        dist1 = abs(getPSval(1) - PSval1)*1
        dist2 = abs(getPSval(2) - PSval2)*1
        dist3 = abs(getPSval(3) - PSval3)*1

        if dist1 < 0.01 and dist2 < 0.01 and dist3 < 0.01:
            break

    return [PSval1, PSval2, PSval3]

# PS current calculation.
# Return the peak current from the "N" th peak
# calculate PS current (any mode)
# Beammode: 0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV)
def calcPS_N(phi2, En, Nth, Beammode):

    if Beammode == 0:
        C3slpList = [0.00733004,0.0072901,0.00733645]
        C3ofsList = [-0.0265696,-0.0218741,-0.0299985]
        C4slpList = [-2.334,-2.32655,-2.332585]
        C4ofsList = [428.953,424.911,420.734]
        C4cfList = [0.0,0.0,0.0,0.0]
    elif Beammode == 1:
        C3slpList = [0.00739327,0.00730657,0.00743984]
        C3ofsList = [-0.134749,-0.0660307,-0.125554]
        C4slpList = [0.43298,0.413311,0.386445]
        C4ofsList = [-288.14,-277.466,-260.41]
        C4cfList = [3.8889e-5,4.5637e-5,5.27254e-5]
    elif Beammode == 2:
        C3slpList = [0.0073892,0.0073166,0.0073441]
        C3ofsList = [-0.0052171,-0.045197,-0.0041411]
        C4slpList = [-2.3796,-2.3714,-2.3794]
        C4ofsList = [445.18,444.51,443.36]
        C4cfList = [0.0,0.0,0.0,0.0]
    elif Beammode == 3:
        C3slpList = [0.0074056,0.0073052,0.0073297]
        C3ofsList = [-0.0079495,-0.050884,-0.0039999]
        C4slpList = [-2.3931,-2.3766,-2.3678]
        C4ofsList = [452.13,445.72,431.04]
        C4cfList = [0.0,0.0,0.0,0.0]
    else:
        print("Beammode is wrong...0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV ")
        sys.exit(99)

    phi0 = 180*Nth
    phi2 += 0
    Ilist = [0.0]*3
# Ilist [0-2]: PS1, PS2, PS3
    Ilist[0] = round(np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[0] + C4slpList[0]*En+ C4cfList[0]*En*En))])/(C3ofsList[0] + C3slpList[0]*En)),3)
    Ilist[1] = round(np.sqrt(max(0,((phi2+180*(Nth))/(C3ofsList[1] + C3slpList[1]*En)))),3)
    Ilist[2] = round(np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[2] + C4slpList[2]*En+ C4cfList[2]*En*En))])/(C3ofsList[2] + C3slpList[2]*En)),3)

    return Ilist

# calculate "N" from PS current (any mode)
# 1と3が大きく変わることは無いので、ひとまず1or2について計算することにする
# Beammode: 0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV)
def calcNforPS(phi2, En, PSch, Itarget, Beammode):

    if Beammode == 0:
        C3slpList = [0.00733004,0.0072901,0.00733645]
        C3ofsList = [-0.0265696,-0.0218741,-0.0299985]
        C4slpList = [-2.334,-2.32655,-2.332585]
        C4ofsList = [428.953,424.911,420.734]
        C4cfList = [0.0,0.0,0.0,0.0]
    elif Beammode == 1:
        C3slpList = [0.00739327,0.00730657,0.00743984]
        C3ofsList = [-0.134749,-0.0660307,-0.125554]
        C4slpList = [0.43298,0.413311,0.386445]
        C4ofsList = [-288.14,-277.466,-260.41]
        C4cfList = [3.8889e-5,4.5637e-5,5.27254e-5]
    elif Beammode == 2:
        C3slpList = [0.0073892,0.0073166,0.0073441]
        C3ofsList = [-0.0052171,-0.045197,-0.0041411]
        C4slpList = [-2.3796,-2.3714,-2.3794]
        C4ofsList = [445.18,444.51,443.36]
        C4cfList = [0.0,0.0,0.0,0.0]
    elif Beammode == 3:
        C3slpList = [0.0074056,0.0073052,0.0073297]
        C3ofsList = [-0.0079495,-0.050884,-0.0039999]
        C4slpList = [-2.3931,-2.3766,-2.3678]
        C4ofsList = [452.13,445.72,431.04]
        C4cfList = [0.0,0.0,0.0,0.0]
    else:
        print("Beammode is wrong...0: lin-1st, 1: lin-3rd, 2: circ (17.1 mm for 180 eV), 3: circ (19.21 mm for 1 keV ")
        sys.exit(99)

    nth = 0
    I1 = -1

    while I1 < Itarget:
        nth += 1
        phi0 = nth * 180
        if PSch == 1 or PSch == 3:
            I1 = round(np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[0] + C4slpList[0]*En+ C4cfList[0]*En*En))])/(C3ofsList[0] + C3slpList[0]*En)),3)
        elif PSch == 2:
            I1 = round(np.sqrt(max(0,((phi2+180*(nth))/(C3ofsList[1] + C3slpList[1]*En)))),3)
        else:
            print("PSch is wrong... input 1, 2 or 3.")
            sys.exit(99)


    if I1 > 20:
        nth -= 1
    
    return nth
