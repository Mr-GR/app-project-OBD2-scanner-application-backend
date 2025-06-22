from pydantic import BaseModel, constr, conlist
from typing import List, Dict

VIN = constr(min_length=17, max_length=17, pattern=r"^[A-HJ-NPR-Z0-9]{17}$")
DTC = constr(pattern=r"^[PBCU][0-9A-F]{4}$")

class DiagnosticsRequest(BaseModel):
    vin: VIN
    codes: conlist(DTC, min_length=1)

class CodeInfo(BaseModel):
    code: DTC
    description: str

class DiagnosticsResponse(BaseModel):
    vin_info: Dict[str, str]
    codes: List[CodeInfo]
