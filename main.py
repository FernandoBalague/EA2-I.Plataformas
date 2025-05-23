from fastapi import FastAPI, Depends, HTTPException, Header, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import httpx
import stripe
import os
from datetime import datetime

app = FastAPI(title="FERREMAS API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulación de base de datos de usuarios
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

@app.post("/auth/login", response_model=AuthResponse)
def login(auth: AuthRequest):
    user = USERS_DB.get(auth.username)
    if user and user["password"] == auth.password:
        return {"token": f"fake-token-for-{auth.username}", "role": user["role"]}
    raise HTTPException(status_code=401, detail="Credenciales inválidas")

async def get_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Token inválido")
    return authorization.split(" ")[1]

FERREMAS_API = "https://ea2p2assets-production.up.railway.app"
FERREMAS_TOKEN = "SaGrP9ojGS39hU9ljqbXxQ=="

@app.get("/external/obtenerProductos", response_model=List[Producto])
async def obtener_productos(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/productos", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error consultando productos externos")

@app.get("/external/obtenerProducto/{producto_id}", response_model=Producto)
async def obtener_producto_por_id(producto_id: int = Path(...), token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/productos/{producto_id}", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=response.status_code, detail="Producto no encontrado")

@app.put("/external/actualizarProductoVenta/{producto_id}", response_model=Producto)
async def actualizar_producto_venta(producto_id: int = Path(...), token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.put(f"{FERREMAS_API}/data/articulos/venta/{producto_id}", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=response.status_code, detail="No fue posible actualizar el producto")

@app.post("/external/crearPedidoNuevo")
async def crear_pedido_nuevo(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{FERREMAS_API}/data/pedidos/nuevo", headers=headers)
        if response.status_code == 200:
            return {"mensaje": "Pedido creado exitosamente en sistema externo"}
        raise HTTPException(status_code=response.status_code, detail="No se pudo crear el pedido")

@app.get("/external/obtenerSucursales", response_model=List[Sucursal])
async def obtener_sucursales(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/sucursales", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error consultando sucursales")

@app.get("/external/obtenerVendedores", response_model=List[Vendedor])
async def obtener_vendedores(token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/vendedores", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=500, detail="Error consultando vendedores")

@app.get("/external/obtenerVendedor/{vendedor_id}", response_model=Vendedor)
async def obtener_vendedor_por_id(vendedor_id: int = Path(...), token: str = Depends(get_token)):
    headers = {"Authorization": f"Bearer {FERREMAS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FERREMAS_API}/vendedores/{vendedor_id}", headers=headers)
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=response.status_code, detail="Vendedor no encontrado")

@app.post("/solicitarContacto")
def solicitar_contacto(datos: SolicitudContacto):
    return {
        "mensaje": "Tu solicitud ha sido recibida. Un vendedor se pondrá en contacto contigo pronto.",
        "datos_recibidos": datos.dict()
    }

@app.post("/realizarPedido", response_model=RespuestaPedido)
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
