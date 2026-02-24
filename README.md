# **User Guide: AI Image Classifier**

update 02/24/26 
The core processing engine has been upgraded to handle large image libraries significantly faster using two main strategies:
1. Multi-threaded Image Proxying

Instead of sending original high-resolution files (which are heavy and slow) directly to the LLM, the app now creates 384px thumbnails.

    Parallel Processing: The app uses all available CPU cores (ThreadPoolExecutor) to generate these miniatures simultaneously.

    I/O Efficiency: Processing 50KB files instead of 10MB+ files reduces data transfer bottlenecks to Ollama by over 90%.

2. Persistent AI Caching

A hidden directory (.cache_ai) is now created within your source folder.

    Skip Redundancy: If you restart the app or re-index the same folder, the AI instantly retrieves existing thumbnails instead of regenerating them.

    Manual Control: A "Clear AI Cache" button has been added to the UI to safely delete these temporary files once your sorting is finalized.


    

## **Overview**

The **AI Image Classifier** is a desktop application designed to help you manage and organize your image library using local Artificial Intelligence. Powered by **Ollama**, it analyzes the visual content of your files to sort them or make them searchable via keywords, all without uploading your data to the cloud.

---

## **1. Core Configuration**

* **Ollama Model**: Select your preferred AI model from the dropdown menu at the top.
* *Note*: For best performance, use multimodal models (capable of seeing images) such as `llava`, `moondream`, or `qwen-vl`.


* **Source Folder**: Click this button to select the directory containing the images you want to process.
* **Destination Folder**: Select where you want the organized images to go. If not selected, the app will create subfolders within the source directory.
* **Include Subfolders**: Check this box if you want the app to recursively scan all folders inside your source directory.

---

## **2. Feature: Automatic Sorting**

This tab is used to physically organize your files into category-based folders.

* **Smart Rename**: When enabled, the AI generates a relevant filename based on the image content (e.g., `golden_retriever_playing_park.jpg`) before moving it.
* **Manage Categories**:
* **Add**: Type a category name in the input field and click "Add".
* **Remove**: Double-click any category in the list to delete it.


* **Start Sorting**: The AI analyzes each image, determines which category it belongs to, and moves it to the appropriate subfolder.

---

## **3. Feature: Keyword Search & Indexing**

This tab allows you to find specific images using natural language descriptions.

* **Indexing**: Click the **Index** button to let the AI "describe" all your images. This creates a local file (`image_index.json`) that stores descriptions. This step is required before searching.
* **Search**: Type any keyword (e.g., "mountain", "car", "blue") in the search bar. The app will display thumbnails of matching images.
* **Batch Actions**:
* Select images using the checkboxes on the thumbnails.
* Use **Copy Selection** or **Move Selection** to quickly export your search results to a specific folder.



---

## **4. Technical Requirements**

* **Ollama**: The Ollama server must be running on your computer.
* **Python Dependencies**: Requires `customtkinter`, `Pillow`, and the `ollama` Python library.
* **Supported Formats**: `.jpg`, `.jpeg`, and `.png`.

---

## **5. Tips for Success**

* **Performance**: AI image analysis is resource-intensive. Using a smaller model like `moondream` will be faster, while `llava` may be more accurate.
* **Duplicates**: If a file with the same name exists in the destination, the app will skip the move to prevent data loss.
