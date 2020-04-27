from flask import Flask, request, jsonify
import json
import os
import sqlite3
from sqlite3 import Error
from werkzeug.utils import secure_filename

app = Flask(__name__)

db_file = 'db/ocr.db'
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'files')
ALLOWED_EXTENSIONS = {'json'}

try:
    os.makedirs('files')
except OSError as e:
    pass

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/api/tests', methods=['POST'])
def create_test():
    subject = request.get_json()['subject']
    answer_keys = request.get_json()['answer_keys']
    answer_keys = json.loads(json.dumps(answer_keys))

    connection = None

    try:
        connection = sqlite3.connect(db_file)
        result = connection.execute("INSERT INTO tests (subject) VALUES (?)", [subject])
        answer_projection = [(question_number, result.lastrowid, answer) for question_number, answer in
                             answer_keys.items()]
        connection.executemany("INSERT INTO answers VALUES (?, ?, ?)", answer_projection)
        connection.commit()

        values = {k: v for k, v in answer_keys.items()}
        response_body = {"test_id": result.lastrowid, "subject": subject, "answer_keys": values, "submissions": []}
        return jsonify(response_body), 200

    except Error as error:
        print(error)

    finally:
        if connection:
            connection.close()
    return "Error occurred", 400


@app.route('/api/tests/<test_id>/scantrons', methods=["POST"])
def upload_scantron(test_id):
    file = request.files['data']
    file.filename = secure_filename(file.filename)
    filepath = "http://localhost:5000/files/" + file.filename
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    data = json.load(open((os.path.join(app.config['UPLOAD_FOLDER'], file.filename))))
    connection = None

    try:
        name = data["name"]
        subject = data["subject"]
        answers = data["answers"]
        connection = sqlite3.connect(db_file)
        correct_answers = connection.execute("SELECT * FROM answers WHERE test_id = ?", [test_id])
        score = 0
        result = {}
        correct_answers = {row[0]: row[2] for row in correct_answers}

        for key in correct_answers:
            if correct_answers[key] == answers[key]:
                score += 1
            result[key] = {"actual": answers[key],
                           "expected": correct_answers[key]}

        submission_values = [test_id, name, filepath, subject, score]
        submission = connection.execute(
            "INSERT INTO submissions (test_id, name, scantron_url, subject, score) VALUES (?,?,?,?,?)",
            submission_values)
        result_values = [(submission.lastrowid, question_number, value) for question_number, value in answers.items()]
        connection.executemany("INSERT INTO result VALUES (?, ?, ?)", result_values)
        connection.commit()
        response = {"scantron_id": submission.lastrowid,
                    "scantron_url": filepath,
                    "name": name,
                    "subject": subject,
                    "score": score,
                    "result": result}
        return jsonify(response), 200

    except Error as error:
        print(error)

    finally:
        if connection:
            connection.close()
    return "Error occurred.", 400


@app.route('/api/tests/<test_id>', methods=["GET"])
def fetch_test(test_id):
    connection = None
    try:
        connection = sqlite3.connect(db_file)
        test = connection.execute("SELECT * FROM tests WHERE test_id = ?", [test_id])
        subject = test.fetchone()[1]
        expected_answers = connection.execute("SELECT * FROM answers WHERE test_id = ?", [test_id])
        submissions = connection.execute("SELECT * FROM submissions WHERE test_id = ?", [test_id])
        expected_answers = {item[0]: item[2] for item in expected_answers}
        submission_result = []

        for submission_row in submissions:
            score = 0
            result = {}
            scantron_id = submission_row[1]
            scantron_url = submission_row[3]
            name = submission_row[2]
            submitted_answers = connection.execute("SELECT * FROM result WHERE scantron_id = ?", [scantron_id])
            submitted_answers = {row[1]: row[2] for row in submitted_answers}

            for key in expected_answers:
                if expected_answers[key] == submitted_answers[key]:
                    score += 1
                result[key] = {"actual": submitted_answers[key],
                               "expected": expected_answers[key]}

            submission_result.append({"scantron_id": submission_row[1],
                                      "scantron_url": scantron_url,
                                      "name": name,
                                      "subject": subject,
                                      "score": score,
                                      "result": result})

        response = {"test_id": test_id,
                    "subject": subject,
                    "answer_keys": expected_answers,
                    "submissions": submission_result}
        return jsonify(response), 200

    except Error as error:
        print(error)

    finally:
        if connection:
            connection.close()
    return "Error occurred", 400
