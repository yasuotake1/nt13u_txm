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
FilePos = "./BL_Parameters/"

# Get proxy setting parameter to connect to 774 server
def getIPaddress():
    IPstr = IP
    ret = xmlrpc.client.ServerProxy(IPstr)
    return ret


# calculate PS current (Circular mode)
# nth を自動検索するかどうか要検討。180-3000 でオールマイティに使える値は無い。現状は電流値で探してみている。
def calcPS_C(phi2, PSC, En, Ith):

# parameters for +-17.1 mm 
#    C3slpList = [0.0073892,0.0073166,0.0073441]
#    C3ofsList = [-0.0052171,-0.045197,-0.0041411]
#    C4slpList = [-2.3796,-2.3714,-2.3794]
#    C4ofsList = [445.18,444.51,443.36]
# parameters for +-19.21 mm 
    C3slpList = [0.0074056,0.0073052,0.0073297]
    C3ofsList = [-0.0079495,-0.050884,-0.0039999]
    C4slpList = [-2.3931,-2.3766,-2.3678]
    C4ofsList = [452.13,445.72,431.04]

    nth = 0
    I1 = -1

    while I1 < Ith:
        phi0 = nth * 180
        I1 = phi0 + (C4ofsList[0] + C4slpList[0]*En)
        I1 = max([0,I1])
        I1 = np.sqrt(I1/(C3ofsList[0] + C3slpList[0]*En))

        nth += 1

    if I1 > 20:
        nth -= 1

    phi0 = 180 * (nth-1)
    
    phi2 += 0
    I1 = np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[0] + C4slpList[0]*En))])/(C3ofsList[0] + C3slpList[0]*En))
    I3 = np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[2] + C4slpList[2]*En))])/(C3ofsList[2] + C3slpList[2]*En))
    I2 = np.sqrt(phi2/(C3ofsList[1] + C3slpList[1]*En))

    if PSC == 1:
        retVal = round(I1,3)
    elif PSC == 3:
        retVal = round(I3,3)
    else:
        retVal = round(I2,3)

    return retVal

# calculate PS current (VH mode)
# nth を自動検索するかどうか要検討。180-3000 でオールマイティに使える値は無い。現状は電流値で探してみている。
def calcPS_VH(phi2, PSC, En, Ith):

    C3slpList = [0.00733004,0.0072901,0.00733645]
    C3ofsList = [-0.0265696,-0.0218741,-0.0299985]
    C4slpList = [-2.334,-2.32655,-2.332585]
    C4ofsList = [428.953,424.911,420.734]

    nth = 0
    I1 = -1

    while I1 < Ith:
        phi0 = nth * 180
        I1 = phi0 + (C4ofsList[0] + C4slpList[0]*En)
        I1 = max([0,I1])
        I1 = np.sqrt(I1/(C3ofsList[0] + C3slpList[0]*En))

        nth += 1

    if I1 > 20:
        nth -= 1

    phi0 = 180 * (nth-1)
    
    phi2 += 0
    I1 = np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[0] + C4slpList[0]*En))])/(C3ofsList[0] + C3slpList[0]*En))
    I3 = np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[2] + C4slpList[2]*En))])/(C3ofsList[2] + C3slpList[2]*En))
    I2 = np.sqrt(phi2/(C3ofsList[1] + C3slpList[1]*En))

    if PSC == 1:
        retVal = round(I1,3)
    elif PSC == 3:
        retVal = round(I3,3)
    else:
        retVal = round(I2,3)

    return retVal

# calculate PS current (VH mode, 3rd)
# nth を自動検索するかどうか要検討。180-3000 でオールマイティに使える値は無い。現状は電流値で探してみている。
def calcPS_VH3(phi2, PSC, En, Ith):

    C3slpList = [0.00739327,0.00730657,0.00743984]
    C3ofsList = [-0.134749,-0.0660307,-0.125554]
    C4cfList = [3.8889e-5,4.5637e-5,5.27254e-5]
    C4slpList = [0.43298,0.413311,0.386445]
    C4ofsList = [-288.14,-277.466,-260.41]

    nth = 0
    I1 = -1

    while I1 < Ith:
        phi0 = nth * 180
        I1 = phi0 + (C4ofsList[0] + C4slpList[0]*En + C4cfList[0]*En*En)
        I1 = max([0,I1])
        I1 = np.sqrt(I1/(C3ofsList[0] + C3slpList[0]*En))

        nth += 1

    if I1 > 20:
        nth -= 1

    phi0 = 180 * (nth-1)
    
    phi2 += 0
    I1 = np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[0] + C4slpList[0]*En+ C4cfList[0]*En*En))])/(C3ofsList[0] + C3slpList[0]*En))
    I3 = np.sqrt(max([0,(phi0 - phi2 + (C4ofsList[2] + C4slpList[2]*En+ C4cfList[2]*En*En))])/(C3ofsList[2] + C3slpList[2]*En))
    I2 = np.sqrt(phi2/(C3ofsList[1] + C3slpList[1]*En))

    if PSC == 1:
        retVal = round(I1,3)
    elif PSC == 3:
        retVal = round(I3,3)
    else:
        retVal = round(I2,3)

    return retVal

# Return 1 if all the IDs are in "V/H" mode (VHVH). Otherwise return 0.
def CheckIfVHmode():

    retVal = 1
    c = getIPaddress()

# Read ID parameters
    IDNameHead = "sr_id_13"
    for i in range(4):
        Ch = int(i+1)
        IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"
        IDphase = c.execute(f"{IDName}","get_phase")
        IDphaseV = float(0.5*(IDphase["upper"] + IDphase["lower"]))
        IDphaseV = abs(IDphaseV)-28*(Ch % 2)
        IDphaseV = (abs(IDphaseV) < 0.01)
        #print(IDphase)
        retVal *= IDphaseV
    
    return retVal

# Return 1 if all the IDs are in "C" mode (LRLR). Otherwise return 0.
def CheckIfCmode():

    retVal = 1
    c = getIPaddress()
    phaseVal = 19.21 #17.10

# Read ID parameters
    IDNameHead = "sr_id_13"
    for i in range(4):
        Ch = int(i+1)
        IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"
        IDphase = c.execute(f"{IDName}","get_phase")
        IDphaseV = float(0.5*(IDphase["upper"] + IDphase["lower"]))
        IDphaseV = phaseVal*((-1)**(Ch % 2)) - IDphaseV
        IDphaseV = (abs(IDphaseV) < 0.01)
        #print(IDphase)
        retVal *= IDphaseV
    
    return retVal

# set ID gaps for target energy (circ. 1st)
def setIDgapsC13(targetEn):
    gap = calcIDgapC1(1, targetEn)
    setIDval(1,gap)
    gap = calcIDgapC1(3, targetEn)
    setIDval(3,gap)

def setIDgapsCall_old(targetEn):
    gap = calcIDgapC1(1, targetEn)
    setIDval(1,gap)
    gap = calcIDgapC1(2, targetEn)
    setIDval(2,gap)
    gap = calcIDgapC1(3, targetEn)
    setIDval(3,gap)
    gap = calcIDgapC1(4, targetEn)
    setIDval(4,gap)

# set ID gap from energy
# wait: false
def setIDgapCsingle(Ch,targetEn):
    targetEn = min(targetEn,1400)
    targetEn = max(targetEn,180)
    IDNameHead = "sr_id_13"
    IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"

    c = getIPaddress()
    CheckSafe = CheckIfCmode()
    setgapPara = {"gap":float(calcIDgapC1(Ch,targetEn)), "wait":False}
    if CheckSafe == True:
        IDgap = c.execute(f"{IDName}","set_gap", setgapPara)
    else:
        print("ID phase mode is wrong! No gap moved.")   

    return IDgap

def setIDgapsCall(targetEn):
    IDNameHead = "sr_id_13"
    IDName1 = f"{IDNameHead}_{str(1).zfill(1)}"
    IDName2 = f"{IDNameHead}_{str(2).zfill(1)}"
    IDName3 = f"{IDNameHead}_{str(3).zfill(1)}"
    IDName4 = f"{IDNameHead}_{str(4).zfill(1)}"
#    print(IDName)

    setgapPara1 = {"gap":float(calcIDgapC1(1,targetEn)), "wait":False}
    setgapPara2 = {"gap":float(calcIDgapC1(2,targetEn)), "wait":False}
    setgapPara3 = {"gap":float(calcIDgapC1(3,targetEn)), "wait":False}
    setgapPara4 = {"gap":float(calcIDgapC1(4,targetEn)), "wait":False}

    c = getIPaddress()

    CheckSafe = CheckIfCmode()
    if CheckSafe == True:
        IDgap1 = c.execute(f"{IDName1}","set_gap", setgapPara1)
        IDgap2 = c.execute(f"{IDName2}","set_gap", setgapPara2)
        IDgap3 = c.execute(f"{IDName3}","set_gap", setgapPara3)
        IDgap4 = c.execute(f"{IDName4}","set_gap", setgapPara4)

        while True:
            time.sleep(2.0)
            _is_moving_ = c.execute(f"{IDName4}","is_moving")
            if _is_moving_ == False:
                break
    else:
        print("ID phase mode is wrong! No gap moved.")

# set ID gap from energy
# wait: false
def setIDgapVH1single(Ch,targetEn):
    targetEn = min(targetEn,1400)
    targetEn = max(targetEn,180)
    IDNameHead = "sr_id_13"
    IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"

    c = getIPaddress()
    CheckSafe = CheckIfVHmode()
    setgapPara = {"gap":float(calcIDgapVH1(Ch,targetEn)), "wait":False}
    if CheckSafe == True:
        IDgap = c.execute(f"{IDName}","set_gap", setgapPara)
    else:
        print("ID phase mode is wrong! No gap moved.")   

    return IDgap

def setIDgapVH3single(Ch,targetEn):
    targetEn = min(targetEn,3050)
    targetEn = max(targetEn,1000)
    IDNameHead = "sr_id_13"
    IDName = f"{IDNameHead}_{str(Ch).zfill(1)}"

    c = getIPaddress()
    CheckSafe = CheckIfVHmode()
    setgapPara = {"gap":float(calcIDgapVH3(Ch,targetEn)), "wait":False}
    if CheckSafe == True:
        IDgap = c.execute(f"{IDName}","set_gap", setgapPara)
    else:
        print("ID phase mode is wrong! No gap moved.")   

    return IDgap

def setIDgapsVHall(targetEn):
    IDNameHead = "sr_id_13"
    IDName1 = f"{IDNameHead}_{str(1).zfill(1)}"
    IDName2 = f"{IDNameHead}_{str(2).zfill(1)}"
    IDName3 = f"{IDNameHead}_{str(3).zfill(1)}"
    IDName4 = f"{IDNameHead}_{str(4).zfill(1)}"
#    print(IDName)

    setgapPara1 = {"gap":float(calcIDgapVH1(1,targetEn)), "wait":False}
    setgapPara2 = {"gap":float(calcIDgapVH1(2,targetEn)), "wait":False}
    setgapPara3 = {"gap":float(calcIDgapVH1(3,targetEn)), "wait":False}
    setgapPara4 = {"gap":float(calcIDgapVH1(4,targetEn)), "wait":False}

#    print(setgapPara1,setgapPara2,setgapPara3,setgapPara4)

    c = getIPaddress()

    CheckSafe = CheckIfVHmode()
    if CheckSafe == True:
        IDgap1 = c.execute(f"{IDName1}","set_gap", setgapPara1)
        IDgap2 = c.execute(f"{IDName2}","set_gap", setgapPara2)
        IDgap3 = c.execute(f"{IDName3}","set_gap", setgapPara3)
        IDgap4 = c.execute(f"{IDName4}","set_gap", setgapPara4)

        while True:
            time.sleep(2.0)
            _is_moving_ = c.execute(f"{IDName3}","is_moving") or c.execute(f"{IDName4}","is_moving")
            if _is_moving_ == False:
                break
    else: 
        print("ID phase mode is wrong! No gap moved.")

def setIDgapsVHall3(targetEn):
    IDNameHead = "sr_id_13"
    IDName1 = f"{IDNameHead}_{str(1).zfill(1)}"
    IDName2 = f"{IDNameHead}_{str(2).zfill(1)}"
    IDName3 = f"{IDNameHead}_{str(3).zfill(1)}"
    IDName4 = f"{IDNameHead}_{str(4).zfill(1)}"
#    print(IDName)

    setgapPara1 = {"gap":float(calcIDgapVH3(1,targetEn)), "wait":False}
    setgapPara2 = {"gap":float(calcIDgapVH3(2,targetEn)), "wait":False}
    setgapPara3 = {"gap":float(calcIDgapVH3(3,targetEn)), "wait":False}
    setgapPara4 = {"gap":float(calcIDgapVH3(4,targetEn)), "wait":False}

#    print(setgapPara1,setgapPara2,setgapPara3,setgapPara4)

    c = getIPaddress()

    CheckSafe = CheckIfVHmode()
    if CheckSafe == True:
        IDgap1 = c.execute(f"{IDName1}","set_gap", setgapPara1)
        IDgap2 = c.execute(f"{IDName2}","set_gap", setgapPara2)
        IDgap3 = c.execute(f"{IDName3}","set_gap", setgapPara3)
        IDgap4 = c.execute(f"{IDName4}","set_gap", setgapPara4)

        while True:
            time.sleep(2.0)
            _is_moving_ = c.execute(f"{IDName3}","is_moving") or c.execute(f"{IDName4}","is_moving")
            if _is_moving_ == False:
                break
    else: 
        print("ID phase mode is wrong! No gap moved.")

# calculate gap value from energy for Circ. 1st (19.21 mm for 1 keV)
def calcIDgapC1(Ch, targetEn):

    ofsL = [34.3515,34.1273,33.9191,34.0288]
    I0L = [7.71785,7.88847,8.11036,7.99655]
    cfL = [2991.58,3023.15,3068.01,3035.82]
    e0L = [-13.598,-30.9349,-54.6686,-40.7543]
    ofs = ofsL[Ch-1]
    I0 = I0L[Ch-1]
    cf = cfL[Ch-1]
    e0 = e0L[Ch-1]

    if (cf/(targetEn - e0)) > 2:
        retVal = ofs - I0*math.log((cf/(targetEn - e0))-2)
        #    w[0] - w[1]*ln((w[2]/(x-w[3]))-2)
    else:
        retVal = 80#100

    retVal = round(retVal, 2)

    return retVal

# calculate gap value from energy for Circ. 1st (17.1 mm for 180 eV)
def calcIDgapC2(Ch, targetEn):

    ofsL = [35.8813,35.7906,35.7026,35.6792]
    I0L = [8.23364,8.19594,8.22859,8.12492]
    cfL = [3040.95,3034.96,3039.26,3014.45]
    e0L = [-25.3105,-23.2088,-26.6025,-18.8888]
    ofs = ofsL[Ch-1]
    I0 = I0L[Ch-1]
    cf = cfL[Ch-1]
    e0 = e0L[Ch-1]

    if (cf/(targetEn - e0)) > 2:
        retVal = ofs - I0*math.log((cf/(targetEn - e0))-2)
        #    w[0] - w[1]*ln((w[2]/(x-w[3]))-2)
    else:
        retVal = 80#100

    retVal = round(retVal, 2)

    return retVal

# calculate gap value from energy for V / H 1st
def calcIDgapVH1(Ch, targetEn):

    ofsL = [30.4233,42.5778,30.2407,42.4518]
    I0L = [6.9808,8.7169,7.1318,8.6431]
    cfL = [3046.18,2940.92,3070.33,2901.61]
    e0L = [-40.4932,13.8063,-57.9024,18.0811]
    ofs = ofsL[Ch-1]
    I0 = I0L[Ch-1]
    cf = cfL[Ch-1]
    e0 = e0L[Ch-1]

    if (cf/(targetEn - e0)) > 2:
        retVal = ofs - I0*math.log((cf/(targetEn - e0))-2)
        #    w[0] - w[1]*ln((w[2]/(x-w[3]))-2)
    else:
        retVal = 80#100

    retVal = round(retVal, 2)

    return retVal

# calculate gap value from energy for V / H 3rd
def calcIDgapVH3(Ch, targetEn):

    ofsL = [29.7687,41.5748,29.4442,41.4544]
    I0L = [6.4893,8.2213,6.3399,8.1708]
    cfL = [8571.62,8361.06,8384.97,8306.67]
    e0L = [-30.6169,86.4357,-5.981,91.6275]
    ofs = ofsL[Ch-1]
    I0 = I0L[Ch-1]
    cf = cfL[Ch-1]
    e0 = e0L[Ch-1]

    if (cf/(targetEn - e0)) > 2:
        retVal = ofs - I0*math.log((cf/(targetEn - e0))-2)
        #    w[0] - w[1]*ln((w[2]/(x-w[3]))-2)
    else:
        retVal = 80#100

    retVal = round(retVal, 2)

    return retVal

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