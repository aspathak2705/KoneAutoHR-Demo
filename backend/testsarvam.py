from sarvamai import SarvamAI

client = SarvamAI(api_subscription_key="sk_o90v0ogk_2HfprjMgf83X3oAr9tZiYWie")

for name in dir(client):
    if "voice" in name.lower():
        print(name)