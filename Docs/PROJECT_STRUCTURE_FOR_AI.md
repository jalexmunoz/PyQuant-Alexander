# PyQuant Alexander - Estructura del Proyecto para Generación de Imagen

## Descripción Visual para AI Generadora de Imágenes

Crea un diagrama de arquitectura de software que muestre un sistema de trading cuantitativo de criptomonedas con las siguientes características:

### Diseño General
- **Layout:** Diagrama jerárquico vertical, estilo "arquitectura de capas"
- **Estilo:** Minimalista, moderno, con bloques rectangulares conectados por flechas
- **Colores sugeridos:**
  - Azul oscuro: Capa de datos (Data Layer)
  - Verde: Capa de núcleo (Core Layer)
  - Naranja: Capa de ejecución (Runners/Execution)
  - Púrpura: Utilidades y servicios (Utils/Services)
  - Gris: Configuración y outputs

### Estructura de Capas (de abajo hacia arriba):

#### 1. CAPA BASE - DATOS (Fondo azul oscuro)
```
┌─────────────────────────────────────┐
│   DATA SOURCES                      │
│   ┌─────────────┐  ┌─────────────┐ │
│   │ TradingView │  │   Binance   │ │
│   │  Webhooks   │  │    API      │ │
│   └──────┬──────┘  └──────┬──────┘ │
│          │                 │        │
│          └────────┬────────┘        │
│                   ▼                 │
│   ┌─────────────────────────────┐  │
│   │  utils/data_fetcher.py      │  │
│   │  • Retry logic              │  │
│   │  • Caching (Output/cache/)  │  │
│   └──────────────┬──────────────┘  │
└──────────────────┼──────────────────┘
```

**Elementos:**
- Fuentes externas (TradingView, Binance) arriba
- Módulo `data_fetcher.py` que consume ambas fuentes
- Caché en disco (`Output/cache/`) debajo del fetcher

---

#### 2. CAPA CORE - NÚCLEO DEL SISTEMA (Fondo verde)
```
                    │
                    ▼
┌───────────────────────────────────────────────────┐
│   CORE ENGINE                                     │
│                                                   │
│   ┌──────────────┐   ┌─────────────────────────┐ │
│   │ Pipeline     │──▶│  Portfolio Backtest     │ │
│   │ • Data       │   │  Engine                 │ │
│   │ • Risk       │   │  • Equity curve         │ │
│   │ • Strategy   │   │  • Position tracking    │ │
│   │ • Portfolio  │   │  • Log returns          │ │
│   └──────┬───────┘   └─────────────────────────┘ │
│          │                                        │
│          ▼                                        │
│   ┌────────────────────────────────────────────┐ │
│   │  Strategy 1: Trend Filter (SMA Crossover) │ │
│   │  • SMA50 / SMA200                          │ │
│   │  • Signal: ON/OFF                          │ │
│   │  • Multi-asset: BTC, ETH, SOL, LINK        │ │
│   └────────────────────────────────────────────┘ │
│                                                   │
│   ┌──────────────┐   ┌────────────────────────┐ │
│   │ Risk Engine  │──▶│  Regime Detection      │ │
│   │ • VaR/CVaR   │   │  • risk_on / risk_off  │ │
│   │ • Stress     │   │  • Volatility regimes  │ │
│   └──────────────┘   └────────────────────────┘ │
└───────────────────────────────────────────────────┘
```

**Elementos:**
- Pipeline central (4 fases: Data → Risk → Strategy → Portfolio)
- Motor de backtest de portafolio
- Estrategia principal (Trend Filter)
- Motor de riesgo con detección de regímenes

---

#### 3. CAPA RUNNERS - EJECUCIÓN (Fondo naranja)
```
                    │
                    ▼
┌───────────────────────────────────────────────────┐
│   RUNNERS (Scripts de Ejecución)                  │
│                                                   │
│   ┌──────────────────────────────┐               │
│   │ run_shadow_mode.py           │               │
│   │ • Procesa webhooks diarios   │               │
│   │ • Genera decisiones          │               │
│   │ • Actualiza portfolio.json   │               │
│   └──────────────┬───────────────┘               │
│                  │                                │
│   ┌──────────────▼───────────────┐               │
│   │ run_strategy1_regime_tests.py│               │
│   │ • Stress tests (2018, 2022)  │               │
│   │ • Out-of-sample validation   │               │
│   └──────────────┬───────────────┘               │
│                  │                                │
│   ┌──────────────▼───────────────┐               │
│   │ Otros runners...             │               │
│   │ • Backtests                  │               │
│   │ • Reportes                   │               │
│   │ • Análisis                   │               │
│   └──────────────────────────────┘               │
└───────────────────────────────────────────────────┘
```

**Elementos:**
- Script principal `run_shadow_mode.py` (validación en modo sombra)
- Runner de tests de régimen
- Otros runners conectados horizontalmente

---

#### 4. CAPA SERVICIOS - UTILIDADES (Fondo púrpura)
```
┌───────────────────────────────────────────────────┐
│   UTILS / SERVICES                                │
│                                                   │
│   ┌─────────────┐  ┌──────────────┐             │
│   │ webhook_    │  │ heartbeat.py │             │
│   │ receiver.py │  │ • Status     │             │
│   │ • Flask API │  │ • Monitoring │             │
│   └──────┬──────┘  └──────┬───────┘             │
│          │                 │                     │
│          ▼                 ▼                     │
│   ┌───────────────────────────────────────────┐  │
│   │ Reporting & Analysis                      │  │
│   │ • QuantStats tearsheets                   │  │
│   │ • Shadow reports                          │  │
│   │ • Weekly summaries                        │  │
│   └───────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

**Elementos:**
- Receptor de webhooks (Flask)
- Sistema de heartbeat
- Módulos de reportes y análisis

---

#### 5. CAPA CONFIGURACIÓN Y OUTPUT (Fondo gris)
```
┌───────────────────────────────────────────────────┐
│   CONFIG & OUTPUT                                 │
│                                                   │
│   ┌──────────────┐      ┌──────────────────────┐ │
│   │ config/      │      │ Output/              │ │
│   │ • portfolio. │      │ • shadow/            │ │
│   │   json       │      │ • webhooks/          │ │
│   │              │      │ • heartbeat/         │ │
│   │              │      │ • quantstats/        │ │
│   │              │      │ • cache/             │ │
│   └──────────────┘      └──────────────────────┘ │
└───────────────────────────────────────────────────┘
```

**Elementos:**
- Directorio de configuración (portfolio.json)
- Directorio de outputs con subdirectorios

---

### Flujos de Datos Principales

1. **Flujo de Webhook (derecha):**
   ```
   TradingView → webhook_receiver.py → events_YYYY-MM-DD.json
                ↓
          run_shadow_mode.py → decisions_YYYY-MM-DD.json
                ↓
          portfolio.json (actualizado)
                ↓
          heartbeat/last_run.json
   ```

2. **Flujo de Backtest (izquierda):**
   ```
   Data Sources → data_fetcher.py → Pipeline
                                      ↓
                          Portfolio Backtest Engine
                                      ↓
                          Regime Tests → QuantStats Reports
   ```

3. **Flujo de Validación (centro):**
   ```
   Shadow Mode → Decisions → Portfolio Update → Equity Curve
   ```

---

### Detalles Técnicos Importantes

- **4 Fases del Pipeline:** Data → Risk → Strategy → Portfolio (mostrar como proceso secuencial)
- **Multi-Asset:** BTC, ETH, SOL, LINK (mostrar como 4 símbolos conectados)
- **Regímenes:** risk_on / risk_off (mostrar como estados binarios)
- **Modo Sombra:** Validación OOS de 90 días antes de capital real
- **Arquitectura:** OOP limpio, type hints, separación de responsabilidades

---

### Texto para Prompt de AI Generadora

```
Create a technical architecture diagram for a quantitative cryptocurrency trading system called "PyQuant Alexander".

Show a vertical layered architecture with:
1. DATA LAYER (blue): TradingView webhooks and Binance API feeding into a data fetcher module with disk caching
2. CORE LAYER (green): A 4-phase pipeline (Data→Risk→Strategy→Portfolio) connected to a portfolio backtest engine, with a Trend Filter strategy (SMA crossover) and Risk Engine with regime detection
3. RUNNERS LAYER (orange): Execution scripts including shadow mode validation and regime stress tests
4. SERVICES LAYER (purple): Webhook receiver (Flask), heartbeat monitoring, and reporting modules
5. CONFIG/OUTPUT LAYER (gray): Configuration files and output directories

Show data flows:
- Right side: TradingView → webhook_receiver → shadow_mode → portfolio updates → heartbeat
- Left side: Data sources → backtest pipeline → regime tests → performance reports
- Center: Shadow mode validation flow

Use clean rectangular blocks connected by arrows. Include labels in English and Spanish. Style: minimalist, modern, technical diagram. Colors: dark blue, green, orange, purple, gray for different layers.

The system processes 4 crypto assets (BTC, ETH, SOL, LINK) with SMA crossover signals and dynamic risk overlay. Show multi-asset connections and regime states (risk_on/risk_off).
```

---

### Resumen Ejecutivo para Documentación

**Propósito de cada componente:**

1. **`core/`**: Motor del sistema
   - Pipeline de 4 fases
   - Estrategias de trading
   - Motor de riesgo y regímenes
   - Engine de backtest

2. **`runners/`**: Puntos de entrada
   - Scripts de ejecución diaria
   - Tests de validación
   - Análisis y reportes

3. **`utils/`**: Servicios auxiliares
   - Obtención de datos
   - Receptor de webhooks
   - Sistema de heartbeat
   - Generación de reportes

4. **`config/`**: Estado persistente
   - Configuración del portafolio
   - Posiciones actuales

5. **`Output/`**: Resultados y logs
   - Decisiones de shadow mode
   - Eventos de webhooks
   - Reportes de performance
   - Heartbeat de estado

---

Este documento está diseñado para ser usado con AI generadoras de imágenes como DALL-E, Midjourney, o Stable Diffusion para crear un diagrama visual de la arquitectura del proyecto.

