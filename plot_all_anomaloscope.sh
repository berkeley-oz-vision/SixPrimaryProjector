#!/bin/bash

DATA_DIR="anomaloscope_data"
PLOT_DIR="plots"

# Create plot directory if it doesn't exist
mkdir -p "$PLOT_DIR"

# Plot all subjects together for fixed mode
echo "Plotting all subjects (fixed mode)..."
python plot_anomaloscope_subjects.py "$DATA_DIR" --mode fixed --save anomaloscope_subjects_fixed.png --save_dir "$PLOT_DIR"

# Plot all subjects together for randomized mode
echo "Plotting all subjects (randomized mode)..."
python plot_anomaloscope_subjects.py "$DATA_DIR" --mode randomized --save anomaloscope_subjects_randomized.png --save_dir "$PLOT_DIR"

# Plot individual subjects for fixed mode
echo "Plotting individual subjects (fixed mode)..."
python plot_anomaloscope_subjects.py "$DATA_DIR" --mode fixed --save anomaloscope_subjects_fixed.png --individual --save_dir "$PLOT_DIR"

# Plot individual subjects for randomized mode
echo "Plotting individual subjects (randomized mode)..."
python plot_anomaloscope_subjects.py "$DATA_DIR" --mode randomized --save anomaloscope_subjects_randomized.png --individual --save_dir "$PLOT_DIR" 