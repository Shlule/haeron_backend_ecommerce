# haeron-backend-ecommerce

Describe your project here.


## TODO - 
mettre ne place un systeme de securite pour l'authentification . du rate limit, complexity limit,
depth limit etc. regarde les limiter de bas de strawberry , tu as aussi graphene-protector qui peux aider 
ensuite si tu as la fois faire des limiter custom

mettre en place le systeme authorization. 

regarde comment fonctionne les app django . le but est de peu etre separer l'app d'authentificaiton des guitare et 
l'app du site de e commerce . le but etatn que si l'un crash l'autre soit toujours accessible . Idealement
ils doivent utiliser la meme base de donne 

Faire l'application d'quthenfication des guitare. commen cela est un autre application reflechir a la communication de la base 
et peut etre mettre en place un service rabbitmq pour la communication des servers .

