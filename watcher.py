Certainly! Below is a Python script using the `watchdog` library to monitor the specified directory and handle file operations as described.

```python
import watchdog.observers
import os
import shutil

def process_new_file(file_path):
    try:
        # Call ingestor.py with the new file path
        os.system(f"python3 ingestor.py --file {file_path}")
        
        # Move the file to the processed directory
        src_path = file_path
        dest_path = os.path.join('data', 'processed', os.path.basename(file_path))
        shutil.move(src_path, dest_path)
    except Exception as e:
        print(f"An error occurred while processing {file_path}: {e}")

def setup_watchdog():
    observer = watchdog.observers.Observer()
    directory = '~/Projects/MFYP/data/raw'

    # Define a callback function for file creation events
    def on_created(event):
        if event.is_directory:
            return
        process_new_file(event.src_path)

    observer.schedule(on_created, path=directory, recursive=False)
    observer.start()

    try:
        while True:
            os.system('pause')  # Keeps the script running until interrupted
    except KeyboardInterrupt:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    setup_watchdog()
```

### Explanation:

- **`watchdog.observers.Observer`**: This is used to monitor the directory for changes.
- **`on_created` function**: This function is called whenever a new file is created in the specified directory.
- **`process_new_file` function**: This handles moving the new file to the `data/processed` directory after processing it.
- **`setup_watchdog` function**: Sets up the observer and starts monitoring the directory.
- **`os.system`**: Used to execute shell commands like calling `ingestor.py`.
- **`shutil.move`**: Moves the file from `~/Projects/MFYP/data/raw` to `data/processed`.
- **`os.system('pause')`**: Keeps the script running until interrupted by the user.

Ensure you have the necessary permissions to read and write files in the specified directories. Adjust paths as needed for your environment.
