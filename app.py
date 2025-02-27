from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app, origins=["https://roommate.fajarshiddiqqq.my.id"])


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


@app.route("/portfolios-preview", methods=["GET"])
def get_portfolios_preview():
    with open("storage/metadata/portfolios.json") as f:
        data = json.load(f)
    data = sorted(data, key=lambda x: x["date"], reverse=True)[:3]

    for portfolio in data:
        portfolio["images"] = [
            image for image in portfolio["images"] if image["featured"]
        ]
        for image in portfolio["images"]:
            image["url"] = os.path.join(request.host_url, "files", image["file_name"])

    return jsonify(data)


@app.route("/portfolios", methods=["GET"])
def get_portfolios():
    with open("storage/metadata/portfolios.json") as f:
        data = json.load(f)

    # Process only required fields and keep only featured images
    processed_data = []
    for portfolio in data:
        featured_images = [
            image for image in portfolio["images"] if image.get("featured")
        ]

        processed_data.append(
            {
                "id": portfolio["id"],
                "date": portfolio["date"],
                "title": portfolio["title"],
                "slug": portfolio["slug"],
                "images": [
                    {"url": os.path.join(request.host_url, "files", img["file_name"])}
                    for img in featured_images
                ],
            }
        )

    # Sort by date (newest first)
    sorted_data = sorted(processed_data, key=lambda x: x["date"], reverse=True)

    return jsonify(sorted_data)

@app.route("/portfolios/<slug>", methods=["GET"])
def get_portfolio(slug):
    with open("storage/metadata/portfolios.json") as f:
        data = json.load(f)

    for portfolio in data:
        if portfolio["slug"] == slug:
            for image in portfolio["images"]:
                image["url"] = os.path.join(request.host_url, "files", image["file_name"])
            for video in portfolio["videos"]:
                video["url"] = os.path.join(request.host_url, "files", video["file_name"])
            return jsonify(portfolio)

    return jsonify({"error": "portfolio not found"}), 404


@app.route("/files/<path:file_name>", methods=["GET"])
def get_file(file_name):
    filepath = os.path.join("storage", "files", file_name)
    if not os.path.exists(filepath):
        return jsonify({"error": "file not found"}), 404

    return send_from_directory("storage/files", file_name)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000)) 
    app.run(host="0.0.0.0", port=port)
