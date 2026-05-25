from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def classroom():
    rows = 4 
    cols = 3     
    return render_template(
        "classroom.html",
        rows=rows,
        cols=cols
    )

if __name__ == "__main__":
    app.run(debug=True)