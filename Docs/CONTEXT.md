# Crypto Quant Framework - Context

## TL;DR
Framework de gestión de portafolio multi-activo (BTC, ETH, SOL, LINK) con Risk Overlay dinámico.  
**Goal:** Alpha puro con Beta baja.  
**Current:** CAGR 57.06%, Beta 0.183 vs BTC.

---

## Pipeline (4 Fases)

```
Data → Risk → Strategy → Portfolio
```

1. **Data:** OHLCV cleaning, log returns, resampling
2. **Risk:** Clasificación de regímenes (vol/trend) → `risk_on`/`risk_off`
3. **Strategy:** Señales de trading
4. **Portfolio:** Pesos dinámicos ajustados por Risk Overlay

---

## Estado Actual: Bloque 4

- [x] Stress Testing (2018, 2022)
- [x] Multi-Factor OLS (descomposición Alpha/Beta)
- [ ] Walk-Forward Analysis (EN CURSO)

---

## Stack

- **Speed:** Polars, DuckDB
- **Backtest:** VectorBT
- **Stats:** Statsmodels (OLS), SciPy (T-test)
- **Reporting:** Pyfolio Reloaded

---

## Validación Anti-Overfitting

1. Walk-Forward (rolling 6 meses)
2. T-Test en Sharpe out-of-sample (p < 0.05)
3. VaR/CVaR en sub-períodos críticos
4. Zero data leakage (non-overlapping features)

---

## Filosofía (Kantian Framework)

**Raw data ≠ Reality**  
Los modelos imponen estructura sobre el caos (igual que la mente kantiana impone categorías sobre la experiencia).

Backtesting = "Critique of Pure Experience"

---

## Workflow

- **SPONSOR (tú):** Decisiones estratégicas
- **ARQUITECTO (tú + thinking):** Diseño de pipeline
- **PROGRAMADOR (Cursor + Sonnet):** Implementación
- **TESTER (tú validas + Sonnet genera):** Testing

---

## Código Standards

- Type hints obligatorios
- OOP limpio (core/, runners/)
- Pytest para todo
- Docstrings Google-style

---

## Next Steps

1. Implementar Walk-Forward rolling 6 meses
2. LSTM para predicción de volatilidad
3. AI Agent (Llama Index) para doc analysis
