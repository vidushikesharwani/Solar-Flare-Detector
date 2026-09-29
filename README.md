<p align="center">
  <a href="https://doi.org/10.5281/zenodo.23019457">
    <img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23019457-007EC6?style=for-the-badge&logo=doi&logoColor=white" alt="DOI: 10.5281/zenodo.23019457" height="32" />
  </a>
  <a href="https://doi.org/10.5281/zenodo.23019457">
    <img src="https://zenodo.org/badge/DOI/10.5281/zenodo.23019457.svg" alt="Zenodo Archive" height="32" />
  </a>
</p>

# Solar Sentinel: Operational 30-Minute Solar Flare Early Warning via Dual-Sensor X-Ray Radiometry on ISRO Aditya-L1

<p align="center">
  <img src="screenshots/dashboard.png" alt="Solar Sentinel Mission Control" width="100%" style="border-radius: 8px; border: 1px solid #334155;" />
</p>

<p align="center">
  <a href="https://doi.org/10.5281/zenodo.23019457"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23019457-007EC6?style=for-the-badge&logo=doi&logoColor=white" alt="DOI" /></a>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/React-19.2-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React 19" />
  <img src="https://img.shields.io/badge/TypeScript-5.x-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Aditya--L1-ISRO%20PRADAN-FF9933?style=for-the-badge" alt="ISRO Aditya-L1" />
  <img src="https://img.shields.io/badge/XGBoost-2.1-FF6600?style=for-the-badge" alt="XGBoost 2.1" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="MIT License" /></a>
</p>

<p align="center">
  <strong>An open-source, publication-grade space weather forecasting platform fusing continuous soft and hard X-ray radiometry from India's maiden solar observatory at Sun-Earth L1.</strong>
</p>

<p align="center">
  <a href="Solar_Sentinel_Research_Paper.docx"><strong>📄 Research Paper (.docx)</strong></a> •
  <a href="solar_sentinel_research_paper.md"><strong>📖 Full Paper (.md)</strong></a> •
  <a href="PRADAN_DATASET_SPECSHEET.md"><strong>📊 Dataset Specsheet</strong></a> •
  <a href="figures/"><strong>🖼️ Publication Figures</strong></a>
</p>

---

## 1. Executive Summary

Operational forecasting of solar eruptive events has historically relied on photospheric vector magnetograms (e.g., SDO/HMI) or single-channel soft X-ray radiometry (e.g., NOAA GOES). While magnetograms trace long-term free magnetic energy accumulation, they suffer from 12-minute cadence latencies and cannot resolve pre-reconnection coronal heating. 

**Solar Sentinel** operationalizes continuous dual-instrument telemetry from India's **ISRO Aditya-L1** spacecraft stationed at the Sun-Earth Lagrangian Point 1 (L1, ~1.5 million km sunward):
- **SoLEXS (1–15 keV Soft X-rays):** Detects thermal precursor plasma heating (10–30 MK) 15–30 minutes before explosive flare onset.
- **HEL1OS (12–200 keV Hard X-rays):** Measures non-thermal thick-target electron beam bremsstrahlung during impulsive reconnection.

Evaluated on **76,784 continuous minutes** (February 2024 – July 2026) benchmarked against NOAA GOES ground truth, Solar Sentinel achieves a **10-fold cross-validation $F_1$ score of $0.772 \pm 0.019$, $\text{ROC AUC} = 0.870$, and $\text{TSS} = 0.554$**, outperforming the published SDO/HMI baseline of Bringewald & Parisot (*MDPI Astronomy* 2025, $F_1 = 0.723$).

On strictly unseen, temporally isolated 24-hour holdout blocks, the system achieves **$F_1 = 0.292$, $\text{TSS} = 0.318$, and $\text{HSS} = 0.255$**, exceeding operational Persistence ($\text{TSS} = 0.137$, **$+132\%$**) and $k$-$\sigma$ thresholding ($\text{TSS} = 0.143$, **$+122\%$**).

---

## 2. Published Benchmark Comparison

Benchmarked under standard protocols established in current space weather literature (**Bringewald & Parisot, *MDPI Astronomy* 2025**):

| Model / System | Protocol | $F_1$ Score | ROC AUC | PR AUC | TSS | HSS | Accuracy |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Bringewald & Parisot (2025)** [1] | 10-Fold CV (SDO/HMI Magnetograms) | 0.723 | 0.811 | 0.834 | — | — | 0.733 |
| **★ Solar Sentinel (Aditya-L1)** | **10-Fold CV (Balanced Standard)** | **0.772 ± 0.019** | **0.870 ± 0.015** | **0.875 ± 0.014** | **0.554 ± 0.035** | **0.554 ± 0.035** | **0.777 ± 0.017** |
| **Solar Sentinel (Aditya-L1)** | **M/X-Class Severe Flare CV** | **0.715** | **0.816** | — | — | — | **0.733** |
| **Solar Sentinel (Aditya-L1)** | **SDBP Holdout (30% Strictly Unseen)** | **0.292** | **0.783** | **0.272** | **0.318** | **0.255** | **0.926** |
| **Solar Sentinel (Aditya-L1)** | **Full-Mission Operational Backtest** | **0.479** | **0.893** | **0.471** | **0.439** | **0.457** | **0.957** |

---

## 3. The 4 Scientific Remedies

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                               FOUR SCIENTIFIC REMEDIES                               │
├─────────────────────────┬──────────────────────────┬─────────────────────────────────┤
│ 1. PGPL Gated Labeling  │ 2. SDBP Daily Partition  │ 3. Skill Scores (TSS & HSS)     │
│ Removes label noise in  │ Prevents leakage & July  │ Evaluates real skill under      │
│ quiet pre-flare periods │ 2026 tail data collapse  │ 95%+ non-flare class imbalance  │
├─────────────────────────┴──────────────────────────┴─────────────────────────────────┤
│ 4. Baselines & Sensor Ablations: Confirms +132% gain over Persistence and proves    │
│    cross-sensor synergy (Dual-sensor TSS 0.318 > SoLEXS 0.283 > HEL1OS 0.289)        │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Remedy 1: Precursor-Gated Positive Labeling (PGPL)
Conventional 30-minute horizon labeling blindly marks quiescent equilibrium periods as positive, injecting label noise. PGPL gates positive labeling via physical soft X-ray departure:
$$y(t) = \mathbb{I}\left[ t \in \mathcal{W}_{\text{active}} \cup \left( \mathcal{W}_{\text{precursor}} \cap \mathcal{G}(t) \right) \right]$$
where the observational gate $\mathcal{G}(t)$ is:
$$\mathcal{G}(t) = \left\{ z^S(t) \ge 0.35 \right\} \cup \left\{ \text{RoC}_5^S(t) \ge 0.01 \right\} \cup \left\{ z_{\text{fused}}(t) \ge 0.35 \right\}$$
*Gate ablation proves PGPL acts as a strict noise filter ($+0.071$ precision gain).*

### Remedy 2: Stratified Daily Block Partitioning (SDBP)
Random splitting causes data leakage across 90-minute rolling windows. Chronological tail splits fail because July 2026 has zero NOAA events. SDBP partitions data into non-overlapping 24-hour diurnal blocks $\mathcal{B}_i$ (1,440 min) partitioned into Active ($\mathcal{B}^A$) and Quiet ($\mathcal{B}^Q$) strata:
$$\mathcal{D}_{\text{train}} = \left( \bigcup_{i: i \bmod 10 < 7} \mathcal{B}_i^A \right) \cup \left( \bigcup_{j: j \bmod 10 < 7} \mathcal{B}_j^Q \right), \quad \mathcal{D}_{\text{test}} = \left( \bigcup_{i: i \bmod 10 \ge 7} \mathcal{B}_i^A \right) \cup \left( \bigcup_{j: j \bmod 10 \ge 7} \mathcal{B}_j^Q \right)$$

### Remedy 3: Standard Meteorological Skill Scores (TSS & HSS)
With only 4.3% flare prevalence, Accuracy and ROC AUC are inflated by quiet backgrounds. Solar Sentinel reports the True Skill Statistic (TSS) and Heidke Skill Score (HSS):
$$\text{TSS} = \frac{\text{TP}}{\text{TP} + \text{FN}} - \frac{\text{FP}}{\text{FP} + \text{TN}} = 0.554 \text{ (CV)} \;/\; 0.318 \text{ (Holdout)}$$
$$\text{HSS} = \frac{2(\text{TP}\cdot\text{TN} - \text{FP}\cdot\text{FN})}{(\text{TP} + \text{FN})(\text{FN} + \text{TN}) + (\text{TP} + \text{FP})(\text{FP} + \text{TN})} = 0.255 \text{ (Holdout)}$$

### Remedy 4: Baseline Benchmarks & Sensor Ablations
- **vs. Persistence ($y_t = y_{t-30}$):** $\text{TSS} = 0.318$ vs $0.137$ (**$+132\%$ ML skill advantage**).
- **vs. $k$-$\sigma$ Thresholding ($F \ge B + 3\sigma$):** $\text{TSS} = 0.318$ vs $0.143$ (**$+122\%$ ML skill advantage**).
- **Sensor Ablation:** Dual-Sensor ($\text{TSS} = 0.318$) strictly outperforms SoLEXS-only ($\text{TSS} = 0.283$) and HEL1OS-only ($\text{TSS} = 0.289$).

---

## 4. Visual Tour & Interface

Solar Sentinel includes a fully responsive web application built with React 19, TypeScript, and Three.js:

| 3D Mission Control (`/`) | Research & Figures Gallery (`/research`) |
|:---:|:---:|
| <img src="screenshots/dashboard.png" width="450"/> | <img src="screenshots/research_figures.png" width="450"/> |
| **Model Verification & Metrics (`/metrics`)** | **Flare Event Catalog (`/flares`)** |
| <img src="screenshots/metrics.png" width="450"/> | <img src="screenshots/flare_timeline.png" width="450"/> |

---

## 5. Key Publication Figures

All 7 publication figures are generated at 300 DPI in `figures/`:

| Benchmark Comparison | Precision-Recall (Holdout) | Sensor Ablation |
|:---:|:---:|:---:|
| <img src="figures/fig1_performance_comparison.png" width="280"/> | <img src="figures/fig2_pr_curve.png" width="280"/> | <img src="figures/fig4_ablation_dual_sensor.png" width="280"/> |
| **Fig. 1: Aditya-L1 vs SDO/HMI** | **Fig. 2: 6.3x PR Gain over Baseline** | **Fig. 4: Dual-Sensor Synergy** |

---

## 6. Quick Start

### One-Click Launch
- **Windows:** Double-click `run.bat`
- **Linux/macOS:** Run `./run.sh`

### Manual Setup
```powershell
# 1. Python environment
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# 2. Frontend
cd frontend
npm install --legacy-peer-deps
npm run dev
```

### Model Pipeline Execution
```powershell
# Train model & compute benchmarks
.\venv\Scripts\python -m pipeline.train_model

# Recompile Word research paper
.\venv\Scripts\python pipeline/build_docx_paper.py
```

---

## 7. Repository Structure

```
Solar-Sentinel/
├── CITATION.cff                         # Machine-readable citation metadata (Zenodo / CFF 1.2.0)
├── LICENSE                              # MIT License
├── Solar_Sentinel_Research_Paper.docx   # Publication-ready manuscript (split layout, OMML math)
├── solar_sentinel_research_paper.md     # Full academic paper in Markdown
├── PRADAN_DATASET_SPECSHEET.md          # ISRO PRADAN Level-1 telemetry specification
├── requirements.txt                     # Python dependencies
├── run.bat / run.sh                     # Full application launchers
├── reset.bat / reset.sh                 # Environment reset scripts
├── pipeline/                            # ML pipeline: ingestion, feature engineering, SDBP, XGBoost
├── backend/                             # FastAPI prediction server and telemetry replay
├── frontend/                            # React 19 + TypeScript + Three.js mission interface
├── figures/                             # 300 DPI publication figures (PDF & PNG)
└── screenshots/                         # Interface screenshots
```

---

## 8. Authors & Institutional Credit

This research was conducted at the **School of Computing Science Engineering and Artificial Intelligence, VIT Bhopal University**:

- **Mayank Anand** $^{1,*}$ — *Lead Architect & Author*  
  Institutional: `mayank.25bai11209@vitbhopal.ac.in` | Personal: `dev.mayankanand@gmail.com`
- **Aditi Jha** $^{1}$
- **Vidushi Kesharwani** $^{1}$
- **Gauri Nandana M** $^{1}$
- **Prakriti Wadhwani** $^{1}$
- **Kasak Fitkariwala** $^{1}$

$^{1}$ *Department of Computer Science & Engineering (Specialization in Artificial Intelligence & Machine Learning), School of Computing Science Engineering and Artificial Intelligence, VIT Bhopal University, Kothrikalan, Sehore, Madhya Pradesh 466114, India*  
$^{*}$ *Correspondence:* `mayank.25bai11209@vitbhopal.ac.in`

---

## 9. Citation

If you use this repository, the dual-instrument telemetry pipeline, or the trained XGBoost model in your research, please cite our software release:

```bibtex
@software{anand2026solarsentinel,
  author    = {Anand, Mayank and Jha, Aditi and Kesharwani, Vidushi and 
               M, Gauri Nandana and Wadhwani, Prakriti and Fitkariwala, Kasak},
  title     = {Solar Sentinel: Operational 30-Minute Solar Flare Early Warning 
               via Dual-Sensor X-Ray Radiometry on ISRO Aditya-L1},
  month     = {sep},
  year      = {2026},
  publisher = {Zenodo},
  version   = {v1.0.0},
  doi       = {10.5281/zenodo.23019457},
  url       = {https://doi.org/10.5281/zenodo.23019457}
}
```

Or cite the research manuscript:

```bibtex
@article{anand2026solarsentinel_paper,
  author    = {Anand, Mayank and Jha, Aditi and Kesharwani, Vidushi and 
               M, Gauri Nandana and Wadhwani, Prakriti and Fitkariwala, Kasak},
  title     = {Solar Sentinel: Operational 30-Minute Solar Flare Early Warning 
               via Dual-Sensor X-Ray Radiometry on ISRO Aditya-L1},
  journal   = {Astronomy},
  year      = {2026},
  publisher = {MDPI},
  doi       = {10.5281/zenodo.23019457},
  url       = {https://github.com/mayankanand-dev/Solar-Flare-Detector}
}
```

---

## 10. License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

<p align="center">
  <strong>Data Credit:</strong> Telemetry sourced from <a href="https://pradan.issdc.gov.in/">ISRO PRADAN</a> (Aditya-L1 mission, HEL1OS and SoLEXS instruments). Ground-truth event catalogs provided by the <a href="https://www.swpc.noaa.gov/">NOAA Space Weather Prediction Center (SWPC)</a>.
</p>
