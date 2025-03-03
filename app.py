from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
from utils import require_token, generate_token
from config import Config
import json
import time
import os


app = Flask(__name__)
CORS(app, origins=["https://roommate.fajarshiddiqqq.my.id", "http://localhost:5173"])


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


@app.route("/portfolios", methods=["GET"])
def get_portfolios():
    with open("storage/metadata/portfolios.json") as f:
        data = json.load(f)

    if request.args.get("preview") == "true":
        data = sorted(data, key=lambda x: x["date"], reverse=True)[:3]

    for portfolio in data:
        for image in portfolio["images"]:
            image["url"] = os.path.join(Config.FILES_URL, image["file_name"])
        for video in portfolio["videos"]:
            video["url"] = os.path.join(Config.FILES_URL, video["file_name"])

    sorted_data = sorted(data, key=lambda x: x["date"], reverse=True)
    return jsonify(sorted_data), 200


@app.route("/portfolios", methods=["POST"])
@require_token
def create_portfolio(auth):
    with open("storage/metadata/portfolios.json", "r") as f:
        portfolios = json.load(f)

    latest_id = max([portfolio["id"] for portfolio in portfolios]) if portfolios else 0
    new_id = latest_id + 1

    title = request.form.get("title")
    if not title:
        return jsonify(error="title is required"), 400
    if any(portfolio["title"] == title for portfolio in portfolios):
        return jsonify(error="Title already exists"), 400

    slug = request.form.get("slug")
    if not slug:
        return jsonify(error="slug is required"), 400
    if any(portfolio["slug"] == slug for portfolio in portfolios):
        return jsonify(error="Slug already exists"), 400

    date = request.form.get("date")
    if not date:
        return jsonify(error="Date is required"), 400
    date = datetime.strptime(date, "%Y-%m-%d")

    description = request.form.get("description")
    location = request.form.get("location")
    client = request.form.get("client")
    category = request.form.get("category")
    tags = request.form.get("tags")
    if tags:
        tags = tags.replace(" ", "").split(",")

    image_list = {}
    for key, value in request.form.items():
        if key.startswith("image_"):
            parts = key.split("_")
            if len(parts) < 3:
                continue

            image_index = f"image_{parts[1]}"
            if image_index not in image_list:
                image_list[image_index] = {}

            image_list[image_index][parts[2]] = value

    for key, file in request.files.items():
        if key.startswith("image_"):
            if key not in image_list:
                image_list[key] = {}

            image_list[key]["file"] = file

    portfolio_images = []
    timestamp = int(time.time())

    for key, image in image_list.items():
        filename = f"{new_id}_{timestamp}_{image['file'].filename}"
        image["file"].save(os.path.join("storage/files", filename))
        portfolio_images.append(
            {
                "file_name": filename,
                "alt": image.get("alt", image["file"].filename),
                "thumbnail": bool(image.get("thumbnail", False)),
            }
        )

    portfolio = {
        "id": new_id,
        "title": title,
        "slug": slug,
        "date": date.strftime("%Y-%m-%d"),
        "description": description,
        "location": location,
        "client": client,
        "category": category,
        "tags": tags,
        "images": portfolio_images,
        "videos": [],
    }

    portfolios.append(portfolio)
    with open("storage/metadata/portfolios.json", "w") as f:
        json.dump(portfolios, f, indent=4)

    return jsonify(portfolio), 201


@app.route("/portfolios/<slug>", methods=["GET"])
def get_portfolio(slug):
    with open("storage/metadata/portfolios.json") as f:
        data = json.load(f)

    for portfolio in data:
        if portfolio["slug"] == slug:
            for image in portfolio["images"]:
                image["url"] = os.path.join(Config.FILES_URL, image["file_name"])
            for video in portfolio["videos"]:
                video["url"] = os.path.join(Config.FILES_URL, video["file_name"])
            return jsonify(portfolio), 200

    return jsonify(error="portfolio not found"), 404


@app.route("/portfolios/<int:id>", methods=["PUT", "DELETE"])
@require_token
def update_portfolio(auth, id):
    with open("storage/metadata/portfolios.json", "r") as f:
        portfolios = json.load(f)

    portfolio = next((p for p in portfolios if p["id"] == id), None)
    if not portfolio:
        return jsonify(error="portfolio not found"), 404

    if request.method == "PUT":
        # Update text fields
        slug = request.form.get("slug")
        if slug and any(p["slug"] == slug for p in portfolios if p["id"] != id):
            return jsonify(error="Slug already exists"), 400
        if slug:
            portfolio["slug"] = slug

        fields = ["title", "date", "description", "location", "client", "category"]
        for field in fields:
            value = request.form.get(field)
            if value:
                portfolio[field] = value

        tags = request.form.get("tags")
        if tags:
            portfolio["tags"] = tags.replace(" ", "").split(",")

        # Process images
        image_list = {}
        for key, value in request.form.items():
            if key.startswith("image_"):
                parts = key.split("_")
                if len(parts) < 2:
                    continue
                image_index = key.split("_")[1]
                if f"image_{image_index}" not in image_list:
                    image_list[f"image_{image_index}"] = {}
                image_list[f"image_{image_index}"][parts[-1]] = value

        # Track remaining images
        remaining_filenames = set()

        for key, value in image_list.items():
            if value["status"] == "old":
                for image in portfolio["images"]:
                    if image["file_name"] == value["filename"]:
                        image["alt"] = value.get("alt", image["file_name"])
                        image["thumbnail"] = (
                            str(value.get("thumbnail", "false")).lower() == "true"
                        )
                        remaining_filenames.add(
                            image["file_name"]
                        )  # Track existing image
                        break
            elif value["status"] == "new":
                file = request.files.get(key)
                if not file:
                    return jsonify(error="file not found"), 400
                filename = f"{id}_{int(time.time())}_{file.filename}"
                file.save(os.path.join("storage/files", filename))
                portfolio["images"].append(
                    {
                        "file_name": filename,
                        "alt": value.get("alt", file.filename),
                        "thumbnail": str(value.get("thumbnail", "false")).lower()
                        == "true",
                    }
                )
                remaining_filenames.add(filename)  # Track new image

        # Identify and delete removed images
        deleted_images = [
            image
            for image in portfolio["images"]
            if image["file_name"] not in remaining_filenames
        ]

        # Remove deleted images from storage
        for image in deleted_images:
            file_path = os.path.join("storage/files", image["file_name"])
            if os.path.exists(file_path):
                os.remove(file_path)

        # Remove deleted images from portfolio
        portfolio["images"] = [
            image
            for image in portfolio["images"]
            if image["file_name"] in remaining_filenames
        ]

        # Save changes
        with open("storage/metadata/portfolios.json", "w") as f:
            json.dump(portfolios, f, indent=4)

        return jsonify(portfolio), 200

    elif request.method == "DELETE":
        # Delete associated files
        for image in portfolio["images"]:
            image_path = os.path.join("storage/files", image["file_name"])
            if os.path.exists(image_path):
                os.remove(image_path)

        for video in portfolio["videos"]:
            video_path = os.path.join("storage/files", video["file_name"])
            if os.path.exists(video_path):
                os.remove(video_path)

        # Remove portfolio from list
        portfolios = [p for p in portfolios if p["id"] != id]

        # Save updated portfolio list
        with open("storage/metadata/portfolios.json", "w") as f:
            json.dump(portfolios, f, indent=4)

        return jsonify(message="portfolio deleted"), 200
    return jsonify(error="method not allowed"), 405


@app.route("/files/<path:file_name>", methods=["GET"])
def get_file(file_name):
    filepath = os.path.join("storage", "files", file_name)
    if not os.path.exists(filepath):
        return jsonify(error="file not found"), 404

    return send_from_directory("storage/files", file_name)


@app.route("/login", methods=["POST"])
def login():
    if not request.json:
        return jsonify(status=False, message="JSON body is required"), 400

    email = request.json.get("email")
    password = request.json.get("password")

    if not email == Config.ADMIN_EMAIL:
        return jsonify(status=False, message="Unauthorized"), 401
    if not password == Config.ADMIN_PASSWORD:
        return jsonify(status=False, message="Wrong password"), 401

    token = generate_token(expires_in=timedelta(days=1), email=email)
    return jsonify(status=True, message="Successfully login", data=token), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
