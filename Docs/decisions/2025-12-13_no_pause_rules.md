# Decision Log — 2025-12-13  
## No Pause Rules (Drawdown Depth + Duration Analysis)

### Contexto
Durante la revisión de métricas de drawdown, se observó que la estrategia presenta:
- Drawdowns profundos (hasta -25.49%)
- Drawdowns largos (502 días underwater)
- Volatilidad anualizada de 19.5%
- Calmar ratio extremadamente bajo (0.05)

Esto indica que la estrategia no solo cae fuerte, sino que **tarda demasiado en recuperarse**, lo cual es un riesgo estructural.

---

### Evidencia (de la tabla de métricas)
- **Max DD**: -25.49%
- **Duración del DD**: 502 días
- **Volatilidad**: 19.5%
- **Skew**: -0.25 (colas negativas)
- **Kurtosis**: 17.91 (eventos extremos frecuentes)

---

### Decisión
No se aplicarán “pause rules” automáticas en esta versión del framework.  
En su lugar, se documentan reglas sugeridas para futuras versiones.

---

### Reglas sugeridas (para futuras iteraciones)
1. **Gatillo por profundidad (shock rápido)**  
   - Si DD = -15% ? reducir exposición al 50% por X días.

2. **Gatillo por emergencia (riesgo extremo)**  
   - Si DD = -20% ? pasar a CASH 100% y pausar reentrada por X días.

3. **Gatillo por duración (mercado podrido)**  
   - Si underwater > 60 días ? limitar exposición a 30–50% hasta recuperar.

---

### Justificación
- La estrategia actual depende del SMA, que funciona bien en tendencias lentas.  
- Pero los crashes rápidos perforan la señal.  
- Y los drawdowns largos indican que no conviene mantener exposición completa durante periodos prolongados sin recuperación.

---

### Próximos pasos
- Evaluar estas reglas en simulaciones OOS.  
- Integrar un módulo de “risk overlays” en v0.2.  
- Comparar impacto en CAGR, DD y whipsaw.

