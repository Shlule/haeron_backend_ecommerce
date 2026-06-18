# Les Handlers
 Ils existent deux types de handlers Les ProductType Handlers et le ComponentHandler.
 Le but des Handlers est de faire la validation et la provision des données pour Les Product.

## Validation des données
Le but principal des handlers est la validation des données envoyer par le front-End concernant
l'ajout des CartItem. 
les input sont les donnes de configuration fournie par le front end.
ensuite nous verifions si donne sont coherente et verifie si les regles DB sont respecter

## Les productType Handlers
Les product Type handlers sont de hanlders de plus haut niveau qui concerne le type de produit mis en vente.
+ bundle_custom
+ bundle_statique
+ custom_component
+ service

## Le Component Handlers
Les component Handlers sont de plus niveua il interagisse avec les Product Component voici quelque exemple: 
+ custom_piece (une seul piece configurable `neck` et les PartModelOption associer)
+ fixed 
+ product_choice (un choix entre plusieurs reference )
+ product_configurable ( un ensemble de piece ou de prodcutChoice. ceci permet de faire la recusion du model)
