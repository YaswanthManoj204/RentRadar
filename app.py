
from flask import Flask, render_template, request
from scraper import scrape_properties

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def home():
    location = "Kochi"
    min_rent = "1000"
    max_rent = "15000"
    accommodation_type = "all"
    sort_by = "rent_asc"
    properties = []
    message = ""

    if request.method == "POST":
        location = request.form.get("location", "").strip() or "Kochi"
        min_rent = request.form.get("min_rent", "1000").strip() or "1000"
        max_rent = request.form.get("max_rent", "15000").strip() or "15000"
        accommodation_type = request.form.get(
            "accommodation_type", "all"
        ).strip()
        sort_by = request.form.get("sort_by", "rent_asc").strip()

    try:
        min_rent_value = int(min_rent)
        max_rent_value = int(max_rent)

        if min_rent_value < 0 or max_rent_value < 0:
            raise ValueError

        if min_rent_value > max_rent_value:
            raise ValueError

        properties = scrape_properties(
            location=location,
            min_rent=min_rent_value,
            max_rent=max_rent_value,
            accommodation_type=accommodation_type,
            sort_by=sort_by,
        )

        if not properties:
            message = (
                "No matching listings were found. Try another location, "
                "accommodation type, or rent range."
            )

    except ValueError:
        message = (
            "Please enter valid rent amounts. Minimum rent must not "
            "exceed maximum rent."
        )
    except Exception:
        app.logger.exception("RentRadar scraper error")
        message = (
            "We couldn't retrieve listings right now. "
            "Please try again shortly."
        )

    return render_template(
        "index.html",
        properties=properties,
        message=message,
        location=location,
        min_rent=min_rent,
        max_rent=max_rent,
        accommodation_type=accommodation_type,
        sort_by=sort_by,
    )


if __name__ == "__main__":
    app.run(debug=True)
