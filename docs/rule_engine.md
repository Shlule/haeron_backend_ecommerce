# Rule Engine

Le rule engine est une part du systeme permettant de servir au front-end la configuration d'un Product. 
il est specialement dedier ou prvisionnement de Rule de ProductConfiguration. 

## Table

Le Rule engine travaille sur plusieurs Table. 
+ ConfigurationResult
+ ConfigurationCondition
+ ConfigurationRule
+ SelectableValue
+ ProductComponent

## Provision de données 
Le but est que le Rule engine fournisse les données necessaire au front_end pour que celui-ci puisse travaille en autonomie.
Il donne des regel de configuration pour un Product en Particulier.

voici un exemple simple je souhaite que pour le Product Guitar_custom. Si le ProductComponent A possede une PartModelOption avec la valueur egale a `foo`.
alors les valeurs disponible pour le component B sont celle-ci

### exemple de data 
```json
[RuleDTO(id=UUID('8cd9844e-caa0-4049-8c44-ffd4aa5169fb'),
         name='',
         conditions=[ConditionDTO(component=<ProductComponent: ProductComponent object (a14039a9-acf8-4f7c-bf3b-23e13e6b4a32)>,
                                  option=<Option: Option object (88dc58ad-0e4f-4ec3-aefe-fbf19aa98e0a)>,
                                  values=[{'code': 'bleu',
                                           'id': 'f618a7f3-be93-4e19-b8c0-1d0c86403954',
                                           'label': 'bleu',
                                           'type': 'option'}],
                                  operator='eq')],
         results=[ResultDTO(component=<ProductComponent: ProductComponent object (a14039a9-acf8-4f7c-bf3b-23e13e6b4a32)>,
                            option=<Option: Option object (ffcf0ef4-b736-404f-9508-875819b07012)>,
                            target_values=[{'code': 'mapple',
                                            'id': 'dfe7288d-30e3-4540-8605-c81a3471525d',
                                            'label': 'mapple',
                                            'type': 'option'}])]),
 RuleDTO(id=UUID('257ffce9-0288-4e68-a28a-c76cd5b6a086'),
         name='',
         conditions=[],
         results=[]),
 RuleDTO(id=UUID('40bbe454-5a0e-4791-8c02-71f51d38d4a7'),
         name='',
         conditions=[],
         results=[])]
```

