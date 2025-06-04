import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from catboost import CatBoostClassifier
from datetime import datetime

train = pd.read_csv('train.csv')
users = pd.read_csv('users.csv')
events = pd.read_csv('events.csv')
event_attendees = pd.read_csv('event_attendees.csv')
user_friends = pd.read_csv('user_friends.csv')

data = train.merge(users, left_on='user', right_on='user_id', how='left')
data = data.merge(events, left_on='event', right_on='event_id', how='left')
data = data.merge(event_attendees, on='event_id', how='left')
data.drop_duplicates(inplace=True)
data['timestamp'] = pd.to_datetime(data['timestamp'])
data['start_time'] = pd.to_datetime(data['start_time'])
data['joinedAt'] = pd.to_datetime(data['joinedAt'])
data['hour_of_day'] = data['start_time'].dt.hour
data['day_of_week'] = data['start_time'].dt.dayofweek
data['days_until_event'] = (data['start_time'] - data['timestamp']).dt.days
data['location'].fillna('unknown', inplace=True)
top_cities = data['city'].value_counts().nlargest(10).index
data['city'] = data['city'].apply(lambda x: x if x in top_cities else 'other')
def count_friends_going(row):
    user_id = row['user']
    event_id = row['event_id']
    friends = user_friends[user_friends['user'] == user_id]['friends'].values
    if len(friends) > 0:
        friends_list = friends[0].split()
        attendees = event_attendees[event_attendees['event_id'] == event_id]['yes'].values
        if len(attendees) > 0:
            attendees_list = attendees[0].split()
            return len(set(friends_list) & set(attendees_list))
    return 0

data['friends_going'] = data.apply(count_friends_going, axis=1)


features = [
    'hour_of_day', 'day_of_week', 'days_until_event', 'city', 
    'gender', 'timezone', 'friends_going', 'total_words', 'user_activity'
]


cat_features = ['city', 'gender']

X = data[features]
y = data['target']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = CatBoostClassifier(
    iterations=500,
    learning_rate=0.05,
    depth=6,
    cat_features=cat_features,
    eval_metric='AUC',
    verbose=50
)

model.fit(X_train, y_train, eval_set=(X_test, y_test))

y_pred = model.predict_proba(X_test)[:, 1]
print(classification_report(y_test, (y_pred > 0.5).astype(int)))
print(f"AUC-ROC: {roc_auc_score(y_test, y_pred):.3f}")

feature_importance = pd.DataFrame({
    'feature': features,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print(feature_importance)