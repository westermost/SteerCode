"""Symfony 2.x complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "symfony": [
            (r'(?:->get\(|->getContainer\(\))', 1.2),
            (r'(?:->getDoctrine|->getEntityManager|->getRepository)\(', 0.5),
            (r'(?:createQueryBuilder|createQuery|DQL|->select\(|->from\(|->join\()', 1.5),
            (r'(?:@ORM\\|@Assert\\|@Route)', 0.3),
            (r'(?:EventSubscriberInterface|getSubscribedEvents)', 1.5),
            (r'(?:CompilerPassInterface|process\(\s*ContainerBuilder)', 2.0),
            (r'(?:FormBuilderInterface|buildForm|addEventListener)', 1.0),
            (r'(?:VoterInterface|vote\(|ACCESS_GRANTED)', 1.2),
            (r'(?:prePersist|postPersist|preUpdate|postUpdate|onFlush)', 1.0),
            (r'(?:ParamConverter|@ParamConverter)', 0.5),
        ],
    },
    hints={
        "symfony": r'(?:use Symfony\\|namespace\s+\w+\\Bundle|use Doctrine\\|extends\s+(?:Controller|AbstractType|Command))',
    },
)
