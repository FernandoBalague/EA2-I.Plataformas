# Proyecto FERREMAS - FastAPI
# Estructura inicial del proyecto con autenticación, consumo de APIs externas, y endpoints RESTful

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import httpx
import bcchapi
import stripe
import os

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

class Product(BaseModel):
    id: int
    nombre: str
    precio: float
    stock: int

class Branch(BaseModel):
    id: int
    nombre: str
    direccion: str

class Seller(BaseModel):
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
    monto: float  # en pesos o moneda equivalente

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

# Consumo de API de FERREMAS entregada
FERREMAS_API = "https://ea2p2assets-production.up.railway.app"
FERREMAS_TOKEN = "SaGrP9ojGS39hU9ljqbXxQ=="

@app.get("/external/products", response_model=List[Product])
async def obtener_productos_externos(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/productos", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error consultando productos externos")

@app.get("/external/branches", response_model=List[Branch])
async def obtener_sucursales(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/sucursales", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error consultando sucursales")

@app.get("/external/sellers", response_model=List[Seller])
async def obtener_vendedores(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/vendedores", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error consultando vendedores")

# Solicitud de contacto con un vendedor
@app.post("/contacto")
def solicitar_contacto(datos: SolicitudContacto):
    return {
        "mensaje": "Tu solicitud ha sido recibida. Un vendedor se pondrá en contacto contigo pronto.",
        "datos_recibidos": datos.dict()
    }

# Colocación de pedido monoproducto con simulación de pago Stripe
@app.post("/pedido", response_model=RespuestaPedido)
def realizar_pedido(pedido: PedidoMonoProducto, token: str = Depends(get_token)):
    try:
        # Crear un pago simulado con Stripe (monto en centavos si es CLP)
        pago = stripe.PaymentIntent.create(
            amount=int(pedido.monto * 100),  # convertir a centavos
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

# Conversión de divisas usando API del Banco Central
@app.get("/conversion", response_model=ConversionDivisa)
async def convertir_moneda(monto: float = Query(...), moneda_origen: str = Query(...), moneda_destino: str = Query(...)):
    url = "https://si3.bcentral.cl/SieteRESTService/rest/datatime"
    # NOTA: este es un ejemplo ilustrativo, ya que el consumo real requiere suscripción o autenticación
    try:
        # Aquí deberías usar la API real del BCCh con tu token/API Key si es necesario
        # Este código simula una tasa de conversión para fines de la prueba
        tasa = 0.0011 if moneda_origen == "CLP" and moneda_destino == "USD" else 890
        resultado = monto * tasa
        return ConversionDivisa(
            moneda_origen=moneda_origen,
            moneda_destino=moneda_destino,
            monto=monto,
            resultado=round(resultado, 2),
            fecha="2025-05-20"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar la tasa de cambio: {str(e)}")

# Inicio
@app.get("/")
def inicio():
    return {"mensaje": "FERREMAS API - Paso 2 en construcción"}
