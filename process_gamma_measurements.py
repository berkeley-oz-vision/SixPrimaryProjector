#!/usr/bin/env python3
"""
Process gamma measurement CSV files to analyze linearity.
Plots Control vs Power with linear reference and computes errors.
"""

import os
import glob
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


def load_gamma_data(csv_path):
    """Load a gamma CSV file and return DataFrame."""
    try:
        # Read CSV, handling trailing commas by specifying usecols
        # Try to include Temperature if it exists, but don't require it
        df = pd.read_csv(csv_path)
        required_cols = ['Control', 'Power']
        if not all(col in df.columns for col in required_cols):
            return pd.DataFrame()  # Return empty DataFrame if required columns don't exist
        # Select required columns and Temperature if available
        cols_to_keep = required_cols.copy()
        if 'Temperature' in df.columns:
            cols_to_keep.append('Temperature')
        df = df[cols_to_keep]
    except (KeyError, ValueError):
        # If reading fails, try again with all columns
        df = pd.read_csv(csv_path)
        if 'Control' not in df.columns or 'Power' not in df.columns:
            return pd.DataFrame()  # Return empty DataFrame if columns don't exist
        cols_to_keep = ['Control', 'Power']
        if 'Temperature' in df.columns:
            cols_to_keep.append('Temperature')
        df = df[cols_to_keep]
    # Ensure numeric types
    df['Control'] = pd.to_numeric(df['Control'], errors='coerce')
    df['Power'] = pd.to_numeric(df['Power'], errors='coerce')
    if 'Temperature' in df.columns:
        # Handle Temperature column - convert 'N/A' to NaN
        df['Temperature'] = pd.to_numeric(df['Temperature'], errors='coerce')
    # Remove any rows with NaN in required columns
    df = df.dropna(subset=['Control', 'Power'])
    return df


def find_mask_combination(target, available_masks):
    """
    Find a combination of available masks that sum to the target value.
    Can use addition (sum of masks) or subtraction (larger mask - smaller mask).
    Returns tuple: (list of masks to add, list of masks to subtract) or None if not possible.
    """
    available_masks = sorted(available_masks)
    
    # Try simple addition: find masks that sum to target
    from itertools import combinations
    for r in range(1, min(len(available_masks) + 1, 8)):  # Limit to 8 masks max
        for combo in combinations(available_masks, r):
            if sum(combo) == target:
                return (list(combo), [])
    
    # Try subtraction: larger_mask - smaller_mask = target
    # This means: larger_mask = target + smaller_mask
    for larger in available_masks:
        if larger > target:
            smaller = larger - target
            if smaller in available_masks:
                return ([larger], [smaller])
    
    # Try combinations with subtraction: sum(add_masks) - sum(sub_masks) = target
    # This is more complex, so limit the search
    for add_count in range(1, min(4, len(available_masks) + 1)):
        for sub_count in range(1, min(4, len(available_masks) + 1)):
            for add_combo in combinations(available_masks, add_count):
                for sub_combo in combinations(available_masks, sub_count):
                    if sum(add_combo) - sum(sub_combo) == target:
                        return (list(add_combo), list(sub_combo))
    
    return None


def calculate_missing_masks(df, max_value=255):
    """
    Calculate power values for missing masks by combining available masks.
    Supports both addition and subtraction of mask powers.
    Returns DataFrame with calculated masks and their powers.
    """
    measured_masks = df['Control'].values
    measured_powers = df['Power'].values
    
    # Create a lookup dictionary
    mask_to_power = dict(zip(measured_masks, measured_powers))
    
    calculated_masks = []
    calculated_powers = []
    mask_combinations = []
    
    # Find all missing values up to max_value
    all_masks = set(range(1, max_value + 1))
    missing_masks = sorted(all_masks - set(measured_masks))
    
    for target in missing_masks:
        combo = find_mask_combination(target, measured_masks)
        if combo is not None:
            add_masks, sub_masks = combo
            # Calculate power: sum of added masks minus sum of subtracted masks
            total_power = sum(mask_to_power[m] for m in add_masks)
            total_power -= sum(mask_to_power[m] for m in sub_masks)
            
            calculated_masks.append(target)
            calculated_powers.append(total_power)
            # Format combination string
            combo_str = " + ".join(str(m) for m in add_masks)
            if sub_masks:
                combo_str += " - " + " - ".join(str(m) for m in sub_masks)
            mask_combinations.append(combo_str)
    
    if calculated_masks:
        return pd.DataFrame({
            'Control': calculated_masks,
            'Power': calculated_powers,
            'Combination': mask_combinations
        })
    return pd.DataFrame()


def compute_linearity_errors(df):
    """
    Compute errors from linearity.
    Assumes linear relationship: Power = (Control / 255) * power_at_255
    We estimate power_at_255 by extrapolating from the max control value.
    """
    control = df['Control'].values
    power = df['Power'].values
    
    # Find max control and corresponding power
    max_control = control.max()
    max_power = power.max()
    
    # Estimate power at 255 assuming linearity: power_at_255 = max_power * (255 / max_control)
    power_at_255 = max_power * (255.0 / max_control) if max_control > 0 else max_power
    
    # Expected linear power: (control / 255) * power_at_255
    expected_power = (control / 255.0) * power_at_255
    
    # Compute errors
    errors = power - expected_power
    relative_errors = (errors / power_at_255) * 100  # Percentage error relative to full scale
    
    return errors, relative_errors, expected_power


def plot_gamma_linearity(df, csv_name, save_path=None, show_plot=False):
    """
    Plot Control vs Power with linear reference line and calculated missing masks.
    """
    control = df['Control'].values
    power = df['Power'].values
    
    # Calculate missing masks
    calculated_df = calculate_missing_masks(df)
    
    # Compute linear reference (normalized to 255)
    max_power = power.max()
    max_control = control.max()
    power_at_255 = max_power * (255.0 / max_control) if max_control > 0 else max_power
    control_range = np.linspace(0, max(control.max(), 255), 100)
    linear_reference = (control_range / 255.0) * power_at_255
    
    # Compute errors
    errors, relative_errors, expected_power = compute_linearity_errors(df)
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Control vs Power with linear reference
    ax1.scatter(control, power, label='Measured Power', color='blue', s=20, zorder=3)
    
    # Plot calculated missing masks if available
    if not calculated_df.empty:
        calc_control = calculated_df['Control'].values
        calc_power = calculated_df['Power'].values
        # Sort for line plotting
        sort_idx = np.argsort(calc_control)
        ax1.plot(calc_control[sort_idx], calc_power[sort_idx], 
                'g-', label='Calculated from Bitmasks', linewidth=1, alpha=0.7, zorder=2)
        ax1.scatter(calc_control, calc_power, color='green', s=10, alpha=0.6, zorder=3)
    
    ax1.plot(control_range, linear_reference, 'r--', label='Linear Reference (y=x*255)', 
             linewidth=1, alpha=0.7, zorder=1)
    ax1.set_xlabel('Control Value', fontsize=12)
    ax1.set_ylabel('Power', fontsize=12)
    ax1.set_title(f'Linearity Check: {csv_name}', fontsize=14)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, max(control.max(), 255))
    
    # Plot 2: Error plot
    ax2.scatter(control, relative_errors, label='Relative Error (%)', color='red', s=20, zorder=3)
    
    # Plot errors for calculated masks
    if not calculated_df.empty:
        calc_control = calculated_df['Control'].values
        calc_power = calculated_df['Power'].values
        calc_expected = (calc_control / 255.0) * power_at_255
        calc_errors = ((calc_power - calc_expected) / power_at_255) * 100
        ax2.scatter(calc_control, calc_errors, color='green', s=10, alpha=0.6, 
                   label='Calculated Error (%)', zorder=3)
    
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5, zorder=1)
    ax2.set_xlabel('Control Value', fontsize=12)
    ax2.set_ylabel('Relative Error (%)', fontsize=12)
    ax2.set_title(f'Linearity Errors: {csv_name}', fontsize=14)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, max(control.max(), 255))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved plot: {save_path}")
        if not calculated_df.empty:
            print(f"  Calculated {len(calculated_df)} missing masks from bitmask combinations")
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return errors, relative_errors, calculated_df


def process_gamma_folder(folder_path, show_plots=False):
    """
    Process all gamma CSV files in a folder.
    """
    folder_path = Path(folder_path)
    csv_files = sorted(glob.glob(str(folder_path / 'gamma*.csv')))
    # Exclude summary files
    csv_files = [f for f in csv_files if 'summary' not in os.path.basename(f).lower()]
    
    if not csv_files:
        print(f"No gamma CSV files found in {folder_path}")
        return
    
    print(f"Found {len(csv_files)} gamma CSV files")
    
    # Create output subfolder
    output_folder = folder_path / 'linearity_analysis'
    output_folder.mkdir(exist_ok=True)
    print(f"Output folder: {output_folder}")
    
    all_summaries = []
    
    for csv_file in csv_files:
        csv_name = os.path.basename(csv_file)
        print(f"\nProcessing {csv_name}...")
        
        # Load data
        df = load_gamma_data(csv_file)
        
        if df.empty:
            print(f"  Warning: {csv_name} is empty or could not be loaded")
            continue
        
        # Compute errors
        errors, relative_errors, expected_power = compute_linearity_errors(df)
        
        # Find mask with maximum deviation
        abs_relative_errors = np.abs(relative_errors)
        max_error_idx = np.argmax(abs_relative_errors)
        max_error_control = df['Control'].iloc[max_error_idx]
        max_error_value = relative_errors[max_error_idx]
        
        # Create summary for this file
        summary = {
            'File': csv_name,
            'Max_Control': df['Control'].max(),
            'Max_Power': df['Power'].max(),
            'Min_Power': df['Power'].min(),
            'Mean_Relative_Error_%': np.mean(np.abs(relative_errors)),
            'Max_Relative_Error_%': np.max(abs_relative_errors),
            'RMS_Relative_Error_%': np.sqrt(np.mean(relative_errors**2)),
            'Worst_Mask': max_error_control,
            'Worst_Mask_Error_%': max_error_value,
            'Num_Points': len(df)
        }
        
        # Add individual mask errors
        for idx, row in df.iterrows():
            mask_summary = summary.copy()
            mask_summary['Mask'] = row['Control']
            mask_summary['Measured_Power'] = row['Power']
            mask_summary['Expected_Power'] = expected_power[idx]
            mask_summary['Absolute_Error'] = errors[idx]
            mask_summary['Relative_Error_%'] = relative_errors[idx]
            all_summaries.append(mask_summary)
        
        print(f"  Max relative error: {summary['Max_Relative_Error_%']:.2f}% at mask {max_error_control}")
        print(f"  Mean absolute relative error: {summary['Mean_Relative_Error_%']:.2f}%")
        
        # Create plot
        plot_path = output_folder / f"{csv_name.replace('.csv', '_linearity.png')}"
        errors, relative_errors, calculated_df = plot_gamma_linearity(df, csv_name, save_path=str(plot_path), show_plot=show_plots)
        
        # Save calculated masks if any
        if not calculated_df.empty:
            calc_path = output_folder / f"{csv_name.replace('.csv', '_calculated_masks.csv')}"
            calculated_df.to_csv(calc_path, index=False)
            print(f"  Saved calculated masks: {calc_path}")
    
    # Create summary CSV
    summary_df = pd.DataFrame(all_summaries)
    summary_path = output_folder / 'gamma_linearity_summary.csv'
    summary_df.to_csv(summary_path, index=False)
    print(f"\nSaved summary CSV: {summary_path}")
    
    # Print overall statistics
    if len(all_summaries) > 0:
        print("\n" + "="*60)
        print("OVERALL STATISTICS")
        print("="*60)
        for csv_name in summary_df['File'].unique():
            file_data = summary_df[summary_df['File'] == csv_name]
            print(f"\n{csv_name}:")
            print(f"  Worst mask: {file_data['Worst_Mask'].iloc[0]} "
                  f"(error: {file_data['Worst_Mask_Error_%'].iloc[0]:.2f}%)")
            print(f"  Mean absolute error: {file_data['Mean_Relative_Error_%'].iloc[0]:.2f}%")
            print(f"  RMS error: {file_data['RMS_Relative_Error_%'].iloc[0]:.2f}%")


def main():
    parser = argparse.ArgumentParser(
        description='Process gamma measurement CSV files to analyze linearity.'
    )
    parser.add_argument(
        'folder_path',
        type=str,
        help='Path to folder containing gamma CSV files'
    )
    parser.add_argument(
        '--show',
        action='store_true',
        help='Show plots interactively (default: save only)'
    )
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.folder_path):
        print(f"Error: {args.folder_path} is not a valid directory")
        return
    
    process_gamma_folder(args.folder_path, show_plots=args.show)


if __name__ == '__main__':
    main()

