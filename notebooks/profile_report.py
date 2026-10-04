"""
Generate an automatic data-quality report for the Bangalore traffic dataset.

Setup (once, with venv active):
    pip install ydata-profiling

Run from the repo root (the traffic-mlops folder):
    python notebooks/profile_report.py

Output: notebooks/profile_report.html  (open it in your browser)
"""
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

try:
    from ydata_profiling import ProfileReport
except ImportError:
    sys.exit("ydata-profiling is not installed. Run: pip install ydata-profiling")

DATA_PATH = Path("data/raw/bangalore_traffic.csv")
OUT_PATH = Path("notebooks/profile_report.html")

if not DATA_PATH.exists():
    sys.exit(f"Cannot find {DATA_PATH}. Run this from the repo root "
             "and make sure `dvc pull` has finished.")

df = pd.read_csv(DATA_PATH)
df["Date"] = pd.to_datetime(df["Date"])

report = ProfileReport(
    df,
    title="Bangalore Traffic Dataset - Profiling Report",
    minimal=False,
    interactions=None,  # skips the huge scatter-matrix, keeps the file small
    correlations={"auto": {"calculate": False},
                  "pearson": {"calculate": True},
                  "spearman": {"calculate": True}},
)
OUT_PATH.parent.mkdir(exist_ok=True)
report.to_file(OUT_PATH)
print(f"Saved report to {OUT_PATH}")
