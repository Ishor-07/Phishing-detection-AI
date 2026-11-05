from flask import Flask, render_template, request, redirect, url_for, jsonify
import pickle
import os
import csv
from datetime import datetime

app = Flask(__name__)

model = None
vectorizer = None
feature_names = None

if os.path.exists('model.pkl') and os.path.exists('vectorizer.pkl'):
    model = pickle.load(open('model.pkl', 'rb'))
    vectorizer = pickle.load(open('vectorizer.pkl', 'rb'))
    try:
        feature_names = vectorizer.get_feature_names_out()
    except Exception:
        feature_names = None

SUSPICIOUS_TERMS = {
    'verify', 'suspend', 'urgent', 'click', 'login', 'password', 'account', 'confirm',
    'limited', 'prize', 'winner', 'congratulations', 'bank', 'security', 'alert',
    'invoice', 'transfer', 'gift', 'free', 'selected', 'expire', 'renew', 'immediately'
}

PREDICTIONS_LOG = 'predictions.csv'

def predict_with_details(email_text: str):
    if not model or not vectorizer:
        return None
    X = vectorizer.transform([email_text])
    pred = int(model.predict(X)[0])
    proba = None
    if hasattr(model, 'predict_proba'):
        classes = list(getattr(model, 'classes_', []))
        idx_one = classes.index(1) if 1 in classes else 0
        proba = float(model.predict_proba(X)[0][idx_one])
    top_tokens = []
    suspicious_hits = []
    try:
        if feature_names is not None and hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            row = X.tocoo()
            present_indices = set(row.col.tolist())
            token_scores = []
            for i in present_indices:
                token_scores.append((feature_names[i], float(importances[i])))
            token_scores.sort(key=lambda t: t[1], reverse=True)
            top_tokens = [t for t, _ in token_scores[:10]]
    except Exception:
        top_tokens = []
    try:
        text_lower = email_text.lower()
        suspicious_hits = sorted({t for t in SUSPICIOUS_TERMS if t in text_lower})[:10]
    except Exception:
        suspicious_hits = []
    return {
        'prediction': pred,
        'probability': proba,
        'top_tokens': top_tokens,
        'suspicious_hits': suspicious_hits,
    }

def log_prediction(email_text, result, probability):
    try:
        new_file = not os.path.exists(PREDICTIONS_LOG)
        with open(PREDICTIONS_LOG, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if new_file:
                writer.writerow(['timestamp', 'result', 'probability', 'length', 'sample'])
            sample = (email_text or '')[:160].replace('\n', ' ').strip()
            writer.writerow([
                datetime.utcnow().isoformat(timespec='seconds') + 'Z',
                result,
                f"{probability:.4f}" if isinstance(probability, float) else '',
                len(email_text or ''),
                sample
            ])
    except Exception:
        pass

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    proba = None
    top_tokens = []
    suspicious_hits = []
    email_text = ''
    error = None
    if request.method == 'POST':
        email_text = request.form.get('email', '').strip()
        if not email_text:
            error = 'Please paste email text.'
        elif len(email_text) > 20000:
            error = 'Email text is too long (max 20,000 chars).'
        else:
            details = predict_with_details(email_text)
            if details is None:
                error = 'Model not found. Train first.'
            else:
                label = 'Phishing Email 🚨' if details['prediction'] == 1 else 'Legitimate Email ✅'
                result = label
                proba = details['probability']
                top_tokens = details['top_tokens']
                suspicious_hits = details['suspicious_hits']
                log_prediction(email_text, label, proba if proba is not None else 0.0)
    return render_template(
        'index.html',
        result=result,
        proba=proba,
        top_tokens=top_tokens,
        suspicious_hits=suspicious_hits,
        email_text=email_text,
        error=error,
    )

@app.route('/history')
def history():
    rows = []
    if os.path.exists(PREDICTIONS_LOG):
        try:
            with open(PREDICTIONS_LOG, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)[-200:]
                rows.reverse()
        except Exception:
            rows = []
    return render_template('history.html', rows=rows)

@app.post('/api/predict')
def api_predict():
    data = request.get_json(silent=True) or {}
    email_text = (data.get('email') or '').strip()
    if not email_text:
        return jsonify({'error': 'email is required'}), 400
    details = predict_with_details(email_text)
    if details is None:
        return jsonify({'error': 'model not loaded'}), 500
    label = 'phishing' if details['prediction'] == 1 else 'legitimate'
    log_prediction(email_text, label, details['probability'] if details['probability'] is not None else 0.0)
    return jsonify({
        'label': label,
        'probability': details['probability'],
        'top_tokens': details['top_tokens'],
        'suspicious_hits': details['suspicious_hits'],
    })

if __name__ == '__main__':
    app.run(debug=True)
