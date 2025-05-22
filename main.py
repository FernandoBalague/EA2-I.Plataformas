# Proyecto FERREMAS - FastAPI
# Estructura inicial del proyecto con autenticación, consumo de APIs externas, y endpoints RESTful

from fastapi import FastAPI, Depends, HTTPException, Header, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import httpx
import stripe
import os
from datetime import datetime

app = FastAPI(title="FERREMAS API", version="1.0")

# Middleware CORS (para desarrollo y pruebas)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de datos en memoria (simulada)
USERS_DB = {
    "javier_thompson": {"password": "aONF4d6aNBIxRjlgjBRRzrS", "role": "admin"},
    "ignacio_tapia": {"password": "f7rWChmQS1JYfThT", "role": "maintainer"},
    "stripe_sa": {"password": "dzkQqDL9XZH33YDzhmsf", "role": "service_account"},
}

# Configuración de Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_1234567890abcdef")

# Modelos
class SolicitudContacto(BaseModel):
    nombre: str
    correo: str
    mensaje: str

class AuthRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    token: str
    role: str

class Producto(BaseModel):
    id: int
    nombre: str
    precio: float
    stock: int

class Sucursal(BaseModel):
    id: int
    nombre: str
    direccion: str

class Vendedor(BaseModel):
    id: int
    nombre: str
    correo: str
    sucursal_id: int

class PedidoMonoProducto(BaseModel):
    producto_id: int
    cantidad: int
    comprador: str
    direccion_envio: str
    correo: str
    monto: float

class RespuestaPedido(BaseModel):
    mensaje: str
    producto_id: int
    cantidad: int
    comprador: str
    pago_id: Optional[str] = None

class ConversionDivisa(BaseModel):
    moneda_origen: str
    moneda_destino: str
    monto: float
    resultado: float
    fecha: str

# Simulación de autenticación básica
@app.post("/auth/login", response_model=AuthResponse)
def login(auth: AuthRequest):
    user = USERS_DB.get(auth.username)
    if user and user["password"] == auth.password:
        return {"token": f"fake-token-for-{auth.username}", "role": user["role"]}
    raise HTTPException(status_code=401, detail="Credenciales inválidas")

# Dependencia para simular autorización
async def get_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Token inválido")
    return authorization.split(" ")[1]

# API externa de FERREMAS
FERREMAS_API = "https://ea2p2assets-production.up.railway.app"
FERREMAS_TOKEN = "SaGrP9ojGS39hU9ljqbXxQ=="

# ... otros endpoints omitidos para brevedad ...

@app.get("/conversionDivisas", response_model=ConversionDivisa)
async def convertir_moneda(monto: float = Query(...), moneda_origen: str = Query(...), moneda_destino: str = Query(...)):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.appnexus.com/currency?code=CLP&show_rate=true")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="No se pudo obtener el tipo de cambio externo")

            data = response.json()
            rate = None
            for item in data.get("response", {}).get("currencies", []):
                if item.get("code") == "CLP" and "rate" in item:
                    rate = float(item["rate"])
                    break

            if rate is None:
                raise HTTPException(status_code=400, detail="No se encontró tasa de cambio para CLP")

            if moneda_origen == "CLP" and moneda_destino == "USD":
                resultado = monto / rate
            elif moneda_origen == "USD" and moneda_destino == "CLP":
                resultado = monto * rate
            else:
                raise HTTPException(status_code=400, detail="Conversión no soportada")

            return ConversionDivisa(
                moneda_origen=moneda_origen,
                moneda_destino=moneda_destino,
                monto=monto,
                resultado=round(resultado, 2),
                fecha=datetime.now().strftime("%Y-%m-%d")
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la conversión: {str(e)}")

@app.get("/")
def inicio():
    return {"mensaje": "FERREMAS API - Paso 2 en construcción"}
