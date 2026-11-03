#!/usr/bin/env python3
"""
Evalua la agregacion por genero sumando TODAS las probabilidades
de las clases que comparten genero (no solo el top-3).

Tres niveles de respuesta:
  especie -> top1 >= U_ESPECIE
  genero  -> suma del genero >= U_GENERO
  rechazo -> ninguna
"""
import json
from collections import defaultdict

d = json.load(open("resultados/calibracion.json", encoding="utf-8"))

# orden de clases: el mismo que uso el modelo
import torch
ck = torch.load("resultados/modelo_I_full.pt", weights_only=False, map_location="cpu")
CLASES = ck["clases"]

def genero(c):
    return c.replace("_spp", "").split()[0]

GEN = [genero(c) for c in CLASES]

def decidir(r, u_esp, u_gen):
    if r["conf"] >= u_esp:
        return "especie", r["pred"]
    acum = defaultdict(float)
    for g, p in zip(GEN, r["probs"]):
        acum[g] += p
    g, p = max(acum.items(), key=lambda x: x[1])
    if p >= u_gen:
        return "genero", g
    return "rechazo", None

print(f"{'U_esp':>6}{'U_gen':>7} | {'CATALOGO':^24} | {'CONGENERE':^18} | {'FUERA':>8}")
print(f"{'':>6}{'':>7} | {'esp ok':>7}{'gen ok':>8}{'rech':>7} | {'gen ok':>8}{'rech':>8} | {'rech':>8}")
print("-" * 72)

for u_esp in [0.5, 0.6, 0.7]:
    for u_gen in [0.5, 0.6, 0.7, 0.8, 0.9]:
        esp_ok = gen_ok = rech = 0
        for r in d["val"]:
            niv, et = decidir(r, u_esp, u_gen)
            if niv == "especie":   esp_ok += (et == r["real"])
            elif niv == "genero":  gen_ok += (et == genero(r["real"]))
            else:                  rech += 1
        n = len(d["val"])

        cg_ok = cg_rech = 0
        for r in d["congenere"]:
            niv, et = decidir(r, u_esp, u_gen)
            if niv == "rechazo":  cg_rech += 1
            elif niv == "genero": cg_ok += (et == r["genero"])
        nc = len(d["congenere"])

        f_rech = sum(decidir(r, u_esp, u_gen)[0] == "rechazo" for r in d["fuera"])
        nf = len(d["fuera"])

        print(f"{u_esp:>6.2f}{u_gen:>7.2f} | {esp_ok/n:>7.1%}{gen_ok/n:>8.1%}{rech/n:>7.1%} | "
              f"{cg_ok/nc:>8.1%}{cg_rech/nc:>8.1%} | {f_rech/nf:>8.1%}")
