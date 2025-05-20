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

@app.get("/external/productos", response_model=List[Producto])
async def obtener_productos(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/productos", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error consultando productos externos")

@app.get("/external/productos/{producto_id}", response_model=Producto)
async def obtener_producto_por_id(producto_id: int = Path(...), token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/productos/{producto_id}", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=response.status_code, detail="Producto no encontrado")

@app.get("/external/sucursales", response_model=List[Sucursal])
async def obtener_sucursales(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/sucursales", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error consultando sucursales")

@app.get("/external/vendedores", response_model=List[Vendedor])
async def obtener_vendedores(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/vendedores", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error consultando vendedores")

@app.get("/external/vendedores/{vendedor_id}", response_model=Vendedor)
async def obtener_vendedor_por_id(vendedor_id: int = Path(...), token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/vendedores/{vendedor_id}", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=response.status_code, detail="Vendedor no encontrado")

@app.post("/contacto")
def solicitar_contacto(datos: SolicitudContacto):
    return {
        "mensaje": "Tu solicitud ha sido recibida. Un vendedor se pondrá en contacto contigo pronto.",
        "datos_recibidos": datos.dict()
    }

@app.post("/pedido", response_model=RespuestaPedido)
def realizar_pedido(pedido: PedidoMonoProducto, token: str = Depends(get_token)):
    try:
        pago = stripe.PaymentIntent.create(
            amount=int(pedido.monto * 100),
            currency="clp",
            receipt_email=pedido.correo,
            metadata={
                "comprador": pedido.comprador,
                "producto_id": str(pedido.producto_id),
                "cantidad": str(pedido.cantidad)
            },
            description="Pago por pedido FERREMAS"
        )
        return RespuestaPedido(
            mensaje="Pedido y pago registrados exitosamente",
            producto_id=pedido.producto_id,
            cantidad=pedido.cantidad,
            comprador=pedido.comprador,
            pago_id=pago.id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el procesamiento del pago: {str(e)}")

@app.get("/conversion", response_model=ConversionDivisa)
async def convertir_moneda(monto: float = Query(...), moneda_origen: str = Query(...), moneda_destino: str = Query(...)):
    try:
        if moneda_origen == "CLP" and moneda_destino == "USD":
            valor_dolar = 900
        elif moneda_origen == "USD" and moneda_destino == "CLP":
            valor_dolar = 1 / 900
        else:
            raise HTTPException(status_code=400, detail="Conversión no soportada por ahora")

        resultado = monto / valor_dolar if moneda_origen == "CLP" else monto * valor_dolar

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
