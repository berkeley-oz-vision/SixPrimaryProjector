import os
import glob
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse


def load_subject_data(data_dir, mode):
    """
    Load all CSVs in data_dir, filter by randomization_mode, and group by subject_id.
    Returns a dict: {subject_id: DataFrame}
    """
    all_files = glob.glob(os.path.join(data_dir, '*.csv'))
    subject_data = {}
    for file in all_files:
        try:
            df = pd.read_csv(file)
        except Exception as e:
            print(f"Could not read {file}: {e}")
            continue
        # Filter by randomization_mode
        df = df[df['randomization_mode'].str.lower() == mode.lower()]
        if df.empty:
            continue
        # Ensure df is a DataFrame, not a numpy array
        if isinstance(df, pd.DataFrame):
            subject_id = str(df['subject_id'].iloc[0])
        else:
            continue
        if subject_id not in subject_data:
            subject_data[subject_id] = df
        else:
            subject_data[subject_id] = pd.concat([subject_data[subject_id], df], ignore_index=True)
    return subject_data


def plot_subjects(subject_data, save_path=None, show_plot=True, individual=False):
    """
    Plot all subjects on one plot (or individually if individual=True).
    Each subject: mean point and std dev ellipse (x=red_percentage, y=yellow_luminance_percent).
    """
    colors = plt.cm.get_cmap('tab10')
    if not individual:
        fig, ax = plt.subplots(figsize=(8, 6))
    for i, (subject_id, df) in enumerate(subject_data.items()):
        x = df['red_percentage']
        y = df['yellow_luminance_percent']
        mean_x = x.mean()
        mean_y = y.mean()
        color = colors(i % 10)
        # Handle single-point data (no ellipse)
        if len(x) < 2:
            if not individual:
                ax.scatter(mean_x, mean_y, label=f'Subject {subject_id}', color=color, marker='o')
            else:
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.scatter(mean_x, mean_y, label=f'Subject {subject_id}', color=color, marker='o')
                ax.set_xlabel('Red Percentage')
                ax.set_ylabel('Yellow Luminance Percent')
                ax.set_xlim(0, 100)
                ax.set_ylim(0, 100)
                ax.set_title(f'Subject {subject_id}')
                ax.legend()
                if save_path:
                    indiv_path = save_path.replace('.png', f'_subject_{subject_id}.png')
                    plt.savefig(indiv_path, dpi=150)
                if show_plot:
                    plt.show()
                plt.close(fig)
            continue
        cov = np.cov(x, y)
        # Ellipse parameters
        vals, vecs = np.linalg.eigh(cov)
        order = vals.argsort()[::-1]
        vals = vals[order]
        vecs = vecs[:, order]
        theta = np.degrees(np.arctan2(*vecs[:, 0][::-1]))
        width = 2 * np.sqrt(vals[0])
        height = 2 * np.sqrt(vals[1])
        if not individual:
            ax.scatter(mean_x, mean_y, label=f'Subject {subject_id}', color=color)
            ellipse = Ellipse((mean_x, mean_y), width, height, angle=theta,
                              edgecolor=color, facecolor='none', lw=2, alpha=0.7)
            ax.add_patch(ellipse)
        else:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.scatter(mean_x, mean_y, label=f'Subject {subject_id}', color=color)
            ellipse = Ellipse((mean_x, mean_y), width, height, angle=theta,
                              edgecolor=color, facecolor='none', lw=2, alpha=0.7)
            ax.add_patch(ellipse)
            ax.set_xlabel('Red Percentage')
            ax.set_ylabel('Yellow Luminance Percent')

            ax.set_title(f'Subject {subject_id}')
            ax.legend()
            if save_path:
                indiv_path = save_path.replace('.png', f'_subject_{subject_id}.png')
                plt.savefig(indiv_path, dpi=150)
            if show_plot:
                plt.show()
            plt.close(fig)
    if not individual:
        ax.set_xlabel('Red Percentage')
        ax.set_ylabel('Yellow Luminance Percent')
        ax.set_title('Anomaloscope Mean Matches by Subject')
        ax.legend()
        if save_path:
            plt.savefig(save_path, dpi=150)
        if show_plot:
            plt.show()
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description='Plot anomaloscope subject matches.')
    parser.add_argument('data_dir', type=str, help='Path to anomaloscope_data folder')
    parser.add_argument('--mode', type=str, choices=['fixed', 'randomized'],
                        required=True, help='Trial environment: fixed or randomized')
    parser.add_argument('--save', type=str, default='anomaloscope_subjects.png', help='Filename to save the plot')
    parser.add_argument('--individual', action='store_true', help='Plot each subject individually')
    parser.add_argument('--save_dir', type=str, default=None, help='Directory to save all plots')
    args = parser.parse_args()

    # Handle save_dir
    save_path = args.save
    if args.save_dir:
        os.makedirs(args.save_dir, exist_ok=True)
        save_path = os.path.join(args.save_dir, os.path.basename(args.save))

    subject_data = load_subject_data(args.data_dir, args.mode)
    if not subject_data:
        print(f"No data found for mode '{args.mode}' in {args.data_dir}")
        return

    # Patch plot_subjects to pass save_dir for individual plots
    def plot_subjects_with_dir(subject_data, save_path=None, show_plot=True, individual=False, save_dir=None, mode="unknown"):
        colors = plt.cm.get_cmap('tab10')
        if not individual:
            fig, ax = plt.subplots(figsize=(8, 6))
        for i, (subject_id, df) in enumerate(subject_data.items()):
            x = df['red_percentage']
            y = df['yellow_luminance_percent']
            mean_x = x.mean()
            mean_y = y.mean()
            color = colors(i % 10)
            # Handle single-point data (no ellipse)
            if len(x) < 2:
                if not individual:
                    ax.scatter(mean_x, mean_y, label=f'Subject {subject_id}', color=color, marker='o')
                else:
                    fig, ax = plt.subplots(figsize=(8, 6))
                    ax.scatter(mean_x, mean_y, label=f'Subject {subject_id}', color=color, marker='o')
                    ax.set_xlabel('Red Percentage')
                    ax.set_ylabel('Yellow Luminance Percent')
                    ax.set_xlim(0, 100)
                    ax.set_ylim(0, 100)
                    ax.set_title(f'Subject {subject_id} - {mode.title()} Mode')
                    ax.legend()
                    if save_path:
                        fname = os.path.basename(save_path)
                        indiv_path = fname.replace('.png', f'_subject_{subject_id}.png')
                        if save_dir:
                            indiv_path = os.path.join(save_dir, indiv_path)
                        plt.savefig(indiv_path, dpi=150)
                    if show_plot:
                        plt.show()
                    plt.close(fig)
                continue
            cov = np.cov(x, y)
            # Ellipse parameters
            vals, vecs = np.linalg.eigh(cov)
            order = vals.argsort()[::-1]
            vals = vals[order]
            vecs = vecs[:, order]
            theta = np.degrees(np.arctan2(*vecs[:, 0][::-1]))
            width = 2 * np.sqrt(vals[0])
            height = 2 * np.sqrt(vals[1])
            if not individual:
                ax.scatter(mean_x, mean_y, label=f'Subject {subject_id}', color=color)
                ellipse = Ellipse((mean_x, mean_y), width, height, angle=theta,
                                  edgecolor=color, facecolor='none', lw=2, alpha=0.7)
                ax.add_patch(ellipse)
            else:
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.scatter(mean_x, mean_y, label=f'Subject {subject_id}', color=color)
                ellipse = Ellipse((mean_x, mean_y), width, height, angle=theta,
                                  edgecolor=color, facecolor='none', lw=2, alpha=0.7)
                ax.add_patch(ellipse)
                ax.set_xlabel('Red Percentage')
                ax.set_ylabel('Yellow Luminance Percent')
                ax.set_xlim(0, 100)
                ax.set_ylim(0, 100)
                ax.set_title(f'Subject {subject_id} - {mode.title()} Mode')
                ax.legend()
                if save_path:
                    fname = os.path.basename(save_path)
                    indiv_path = fname.replace('.png', f'_subject_{subject_id}.png')
                    if save_dir:
                        indiv_path = os.path.join(save_dir, indiv_path)
                    plt.savefig(indiv_path, dpi=150)
                if show_plot:
                    plt.show()
                plt.close(fig)
        if not individual:
            ax.set_xlim(0, 100)
            ax.set_ylim(0, 100)
            ax.set_xlabel('Red Percentage')
            ax.set_ylabel('Yellow Luminance Percent')
            ax.set_title(f'Anomaloscope Mean Matches by Subject - {mode.title()} Mode')
            ax.legend()
            if save_path:
                plt.savefig(save_path, dpi=150)
            if show_plot:
                plt.show()
            plt.close(fig)

    plot_subjects_with_dir(subject_data, save_path=save_path, show_plot=True,
                           individual=args.individual, save_dir=args.save_dir, mode=args.mode)


if __name__ == '__main__':
    main()
