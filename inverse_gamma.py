import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def createRemappedLUT(csv_file_path):
    # Read the CSV file into a pandas DataFrame
    df = pd.read_csv(csv_file_path)

    # Assuming the lookup table values are in a column named 'Power'
    lookup_table = df['Power'].to_numpy()

    # Calculate the expected linear function values from 0 to 1
    linear_function = np.linspace(lookup_table[0], lookup_table[-1], 256)

    # Initialize the inverse lookup table
    inverse_lookup_table = np.empty_like(linear_function).astype(int)

    # Create the inverse lookup table
    for i in range(256):
        # Find the closest value in the original lookup table to the linear function value
        closest_index = np.argmin(np.abs(lookup_table - linear_function[i]))
        inverse_lookup_table[i] = closest_index

    # Create an array of the actual values from the lookup_table indexed by inverse_lookup_table
    actual_values_from_lookup = lookup_table[inverse_lookup_table]

    # Plot the original and inverse lookup tables side by side
    fig, axs = plt.subplots(1, 2, figsize=(12, 6))

    # Plot the original lookup table
    axs[0].plot(np.arange(256), lookup_table, label='Original Lookup Table')
    axs[0].set_title('Original Lookup Table')
    axs[0].set_xlabel('Index')
    axs[0].set_ylabel('Value')
    axs[0].legend()

    # Plot the inverse lookup table
    axs[1].plot(np.arange(256), actual_values_from_lookup, label='Remapped Lookup Table', color='orange')
    axs[1].set_title('Remapped Lookup Table')
    axs[1].set_xlabel('Index')
    axs[1].set_ylabel('Value')
    axs[1].legend()

    # Display the plots
    plt.tight_layout()
    plt.show()

    return inverse_lookup_table

csv_file_path = "./measurements/gammas/gamma_0.csv"
inverse_lookup = createRemappedLUT(csv_file_path)

# format for tianyun to copy
print('{' + ','.join(map(str, inverse_lookup)) + '}')
