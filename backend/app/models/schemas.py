from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class EntryInput(BaseModel):
    jalur: str
    kondisi: str  # baik / sedang / buruk
    keterangan: str

class EntryOutput(BaseModel):
    id: str
    no: int
    jalur: str
    lintang: str
    bujur: str
    kondisi: str
    keterangan: str
    foto_path: str
