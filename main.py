from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

os.environ
client = MongoClient(os.environ["MONGO_URI"])
#client = MongoClient("mongodb://ISIS2304E03202610:ZkliY56PYRLO@157.253.236.88:8087")

db = client["ISIS2304E03202610"]


@app.get("/")
def inicio():
    return {"estado": "API funcionando correctamente"}


# RF4 - Consultar reseñas de un hotel
@app.get('/hoteles/{hotel_id}/resenas')
def get_resenas_hotel(hotel_id: int):
    resenas = list(db["Resena"].find({"id_hotel": hotel_id, "estado": "publicada"}).sort("fecha_creacion", -1))

    for resena in resenas:
        resena["_id"] = str(resena["_id"])

    return resenas


# RF1 - Crear reseña
@app.post('/hoteles/{hotel_id}/resenas')
def post_resena(hotel_id: int, datos: dict):
    datos["id_hotel"] = hotel_id
    datos["fecha_creacion"] = datetime.now()
    datos["estado"] = "publicada"
    datos["destacada"] = False
    datos["total_votos"] = 0
    datos["votos_clientes"] = []
    datos["respuesta_admin"] = None
    
    existente = db["Resena"].find_one({"codigo_confirmacion": datos["codigo_confirmacion"]})

    if existente:
        return {"mensaje": "Esta reserva ya tiene una reseña registrada"}

    db["Resena"].insert_one(datos)
    return {"mensaje": "Reseña guardada"}


# RF2 - Editar reseña
@app.put('/resenas/{resena_id}')
def put_resena(resena_id: str, datos: dict):
    cambios = {}

    if "texto" in datos:
        cambios["texto"] = datos["texto"]

    if "calificacion" in datos:
        cambios["calificacion"] = datos["calificacion"]

    db["Resena"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": cambios}
    )

    return {"mensaje": "Reseña actualizada"}


# RF3 y RF8 - Eliminar reseña
@app.delete('/resenas/{resena_id}')
def delete_resena(resena_id: str):
    db["Resena"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {"estado": "eliminada"}}
    )

    return {"mensaje": "Reseña eliminada"}


# RF5 - Marcar reseña como útil
@app.post('/resenas/{resena_id}/voto')
def post_voto(resena_id: str, datos: dict):
    resena = db["Resena"].find_one({"_id": ObjectId(resena_id)})
    id_cliente = datos["id_cliente"]

    if id_cliente in resena["votos_clientes"]:
        return {"mensaje": "El cliente ya marcó esta reseña como útil"}

    db["Resena"].update_one(
        {"_id": ObjectId(resena_id)},
        {
            "$push": {"votos_clientes": id_cliente},
            "$inc": {"total_votos": 1}
        }
    )

    return {"mensaje": "Voto guardado"}


# RF6 - Consultar historial de reseñas propias
@app.get('/clientes/{cliente_id}/resenas')
def get_resenas_cliente(cliente_id: int):
    resenas = list(db["Resena"].find({"id_cliente": cliente_id}).sort("fecha_creacion", -1))

    for resena in resenas:
        resena["_id"] = str(resena["_id"])

    return resenas


# RF7 - Responder reseña
@app.put('/resenas/{resena_id}/respuesta')
def put_respuesta(resena_id: str, datos: dict):
    respuesta = {
        "texto": datos["texto"],
        "fecha_respuesta": datetime.now()
    }

    db["Resena"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {"respuesta_admin": respuesta}}
    )

    return {"mensaje": "Respuesta guardada"}


# RF9 - Destacar reseña
@app.put('/resenas/{resena_id}/destacar')
def put_destacar(resena_id: str):
    resena = db["Resena"].find_one({"_id": ObjectId(resena_id)})
    hotel_id = resena["id_hotel"]

    db["Resena"].update_many(
        {"id_hotel": hotel_id},
        {"$set": {"destacada": False}}
    )

    db["Resena"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {"destacada": True}}
    )

    return {"mensaje": "Reseña destacada"}


# RFC1 - Top 10 hoteles con mejor calificación promedio
@app.get('/rfc/top-hoteles')
def get_top_hoteles():
    consulta = list(db["Resena"].aggregate([
        {
            "$match": {
                "estado": "publicada",
                "fecha_creacion": {
                    "$gte": datetime(2024, 1, 1),
                    "$lte": datetime(2024, 12, 31)
                }
            }
        },
        {
            "$group": {
                "_id": "$id_hotel",
                "promedio_calificacion": {"$avg": "$calificacion"},
                "total_resenas": {"$sum": 1}
            }
        },
        {"$sort": {"promedio_calificacion": -1}},
        {"$limit": 10},
        {
            "$project": {
                "_id": 0,
                "id_hotel": "$_id",
                "promedio_calificacion": {"$round": ["$promedio_calificacion", 2]},
                "total_resenas": 1
            }
        }
    ]))

    return consulta


# RFC2 - Evolución de reputación mes a mes de un hotel
@app.get('/rfc/evolucion/{hotel_id}')
def get_evolucion_hotel(hotel_id: int):
    consulta = list(db["Resena"].aggregate([
        {
            "$match": {
                "id_hotel": hotel_id,
                "estado": "publicada",
                "fecha_creacion": {
                    "$gte": datetime(2024, 1, 1),
                    "$lte": datetime(2024, 12, 31)
                }
            }
        },
        {
            "$group": {
                "_id": {"$month": "$fecha_creacion"},
                "promedio_calificacion": {"$avg": "$calificacion"},
                "total_resenas": {"$sum": 1}
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "mes": "$_id",
                "promedio_calificacion": {"$round": ["$promedio_calificacion", 2]},
                "total_resenas": 1
            }
        }
    ]))

    return consulta


# RFC3 - Perfil comparativo de hoteles por ciudad
# Para Bogota usamos como ejemplo los hoteles 2 y 6
@app.get('/rfc/comparativo-bogota')
def get_comparativo_bogota():
    consulta = list(db["Resena"].aggregate([
        {
            "$match": {
                "estado": "publicada",
                "id_hotel": {"$in": [2, 6]}
            }
        },
        {
            "$group": {
                "_id": "$id_hotel",
                "promedio_calificacion": {"$avg": "$calificacion"},
                "total_resenas": {"$sum": 1},
                "resenas_con_respuesta": {
                    "$sum": {
                        "$cond": [{"$ne": ["$respuesta_admin", None]}, 1, 0]
                    }
                },
                "resenas_destacadas": {
                    "$sum": {
                        "$cond": ["$destacada", 1, 0]
                    }
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "promedio_ciudad": {"$avg": "$promedio_calificacion"},
                "hoteles": {"$push": "$$ROOT"}
            }
        },
        {"$unwind": "$hoteles"},
        {
            "$project": {
                "_id": 0,
                "id_hotel": "$hoteles._id",
                "promedio_calificacion": {"$round": ["$hoteles.promedio_calificacion", 2]},
                "total_resenas": "$hoteles.total_resenas",
                "porcentaje_con_respuesta": {
                    "$round": [
                        {
                            "$multiply": [
                                {"$divide": ["$hoteles.resenas_con_respuesta", "$hoteles.total_resenas"]},
                                100
                            ]
                        },
                        1
                    ]
                },
                "porcentaje_destacadas": {
                    "$round": [
                        {
                            "$multiply": [
                                {"$divide": ["$hoteles.resenas_destacadas", "$hoteles.total_resenas"]},
                                100
                            ]
                        },
                        1
                    ]
                },
                "promedio_ciudad": {"$round": ["$promedio_ciudad", 2]},
                "debajo_promedio_ciudad": {
                    "$lt": ["$hoteles.promedio_calificacion", "$promedio_ciudad"]
                }
            }
        },
        {"$sort": {"promedio_calificacion": -1}}
    ]))

    return consulta
