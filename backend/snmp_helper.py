# from pysnmp.hlapi import (
#     getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
#     ContextData, ObjectType, ObjectIdentity
# )

# def get_printer_counter(ip: str, oid: str = '1.3.6.1.2.1.43.10.2.1.4.1.1') -> int:
#     try:
#         iterator = getCmd(
#             SnmpEngine(),
#             CommunityData('public', mpModel=1),
#             # Timeout set to 0.8 seconds with 0 retries so offline printers don't stall the app
#             UdpTransportTarget((ip, 161), timeout=0.8, retries=0),
#             ContextData(),
#             ObjectType(ObjectIdentity(oid))
#         )
        
#         errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
#         if errorIndication or errorStatus:
#             return -1  # Offline or unreachable
        
#         for varBind in varBinds:
#             return int(varBind[1])
            
#     except Exception:
#         return -1  # Connection refused or host down

import asyncio
import concurrent.futures
from pysnmp.hlapi.asyncio import (
    getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity
)

async def _fetch_printer_counter(ip: str, oid: str) -> int:
    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
        SnmpEngine(),
        CommunityData('public', mpModel=1),
        UdpTransportTarget((ip, 161), timeout=0.8, retries=0),
        ContextData(),
        ObjectType(ObjectIdentity(oid))
    )
    
    if errorIndication or errorStatus:
        return -1  # Offline or unreachable
    
    for varBind in varBinds:
        return int(varBind[1])
        
    return -1

def get_printer_counter(ip: str, oid: str = '1.3.6.1.2.1.43.10.2.1.4.1.1') -> int:
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, _fetch_printer_counter(ip, oid)).result()
        else:
            return asyncio.run(_fetch_printer_counter(ip, oid))
            
    except Exception:
        return -1  # Connection refused or host down
