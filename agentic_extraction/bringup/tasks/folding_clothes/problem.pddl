(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    short_pants1 - short_pants
    blouse1 - blouse
    trouser1 - trouser
    dress1 - dress
    brassiere1 - brassiere
    tank_top1 - tank_top
    bed1 - bed
    bedroom - location
  )
  (:init
    (at robot1 bedroom)
    (at bed1 bedroom)
    (at short_pants1 bedroom)
    (at blouse1 bedroom)
    (at trouser1 bedroom)
    (at dress1 bedroom)
    (at brassiere1 bedroom)
    (at tank_top1 bedroom)
    (on_top short_pants1 bed1)
    (on_top blouse1 bed1)
    (on_top trouser1 bed1)
    (on_top dress1 bed1)
    (on_top brassiere1 bed1)
    (on_top tank_top1 bed1)
    (robot_free robot1)
  )
  (:goal
  (and
    (folded short_pants1)
    (folded blouse1)
    (folded trouser1)
    (folded dress1)
    (folded brassiere1)
    (folded tank_top1)
    (on_top short_pants1 bed1)
    (on_top blouse1 bed1)
    (on_top trouser1 bed1)
    (on_top dress1 bed1)
    (on_top brassiere1 bed1)
    (on_top tank_top1 bed1)
  )
)
)
