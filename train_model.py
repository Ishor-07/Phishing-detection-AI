import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import pickle

# Load and split data
df = pd.read_csv('emails.csv')
X_train, X_test, y_train, y_test = train_test_split(
    df['email_text'], df['label'], test_size=0.2, random_state=42)

# Vectorize
vectorizer = TfidfVectorizer(stop_words='english', max_df=0.9)
X_train_tfidf = vectorizer.fit_transform(X_train)

# Train model
clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train_tfidf, y_train)

# Save model and vectorizer
pickle.dump(clf, open('model.pkl', 'wb'))
pickle.dump(vectorizer, open('vectorizer.pkl', 'wb'))

print("Model and vectorizer saved successfully!")
print(f"Training accuracy: {clf.score(X_train_tfidf, y_train):.4f}")
print(f"Test accuracy: {clf.score(vectorizer.transform(X_test), y_test):.4f}")
