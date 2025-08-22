import json

def print_json_structure(data, indent=""):
    """
    Recursively prints the keys of a JSON object or list to show its structure.

    Args:
        data: The JSON data (loaded as a dictionary or list).
        indent (str): The string used for indentation to represent nesting level.
    """
    if isinstance(data, dict):
        # If the data is a dictionary, iterate through its key-value pairs
        for key, value in data.items():
            print(f"{indent}- {key}:")
            # Make a recursive call for any nested dictionaries or lists
            print_json_structure(value, indent + "  ")
    elif isinstance(data, list) and data:
        # If the data is a non-empty list, we inspect the first element
        # to infer the structure of the objects it contains.
        print(f"{indent}- [Array of Objects]:")
        print_json_structure(data[0], indent + "  ")

def main():
    """
    Main function to load a list of JSON files and print their structure.
    """
    # List of the JSON files you want to analyze
    json_files = [
        'morpho_complete_analysis.json',
        'pendle_morpho_summary.json',
        'pendle_morpho_analysis.json'
    ]

    # Loop through each file in the list
    for file_path in json_files:
        try:
            with open(file_path, 'r') as f:
                json_data = json.load(f)
            
            # Print a header for each file
            print(f"\nColumns for: {file_path}")
            print("=" * (len(file_path) + 14))
            
            # Print the structure of the current JSON file
            print_json_structure(json_data)
            
        except FileNotFoundError:
            print(f"\nError: The file '{file_path}' was not found.")
        except json.JSONDecodeError:
            print(f"\nError: The file '{file_path}' is not a valid JSON file.")
        except Exception as e:
            print(f"\nAn unexpected error occurred with '{file_path}': {e}")

if __name__ == "__main__":
    main()
