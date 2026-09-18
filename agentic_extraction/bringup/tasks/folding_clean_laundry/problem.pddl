(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    tablecloth1 - tablecloth
    sock1 - sock
    sock2 - sock
    trouser1 - trouser
    dishtowel1 - dishtowel
    dishtowel2 - dishtowel
    bed1 - bed
    bedroom - location
  )
  (:init
    (at robot1 bedroom)
    (at bed1 bedroom)
    (at tablecloth1 bedroom)
    (at sock1 bedroom)
    (at sock2 bedroom)
    (at trouser1 bedroom)
    (at dishtowel1 bedroom)
    (at dishtowel2 bedroom)
    (on_top tablecloth1 bed1)
    (on_top sock1 bed1)
    (on_top sock2 bed1)
    (on_top trouser1 bed1)
    (on_top dishtowel1 bed1)
    (on_top dishtowel2 bed1)
    (robot_free robot1)
  )
  (:goal
  (and
    (folded tablecloth1)
    (folded sock1)
    (folded sock2)
    (folded trouser1)
    (folded dishtowel1)
    (folded dishtowel2)
    (on_top tablecloth1 bed1)
    (on_top sock1 bed1)
    (on_top sock2 bed1)
    (on_top trouser1 bed1)
    (on_top dishtowel1 bed1)
    (on_top dishtowel2 bed1)
  )
)
)
