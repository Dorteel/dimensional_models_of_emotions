(define (problem pb01)
  (:domain domain_pddl)
  (:objects
    robot1 - robot
    sack1 - sack
    sack2 - sack
    checkout1 - checkout
    canned_food1 - canned_food
    egg1 - egg
    apple1 - apple
    bottle_of_orange_juice1 - bottle_of_orange_juice
    grocery_store - location
  )
  (:init
    (on_top sack1 checkout1)
    (on_top sack2 checkout1)
    (on_top canned_food1 checkout1)
    (on_top egg1 checkout1)
    (on_top apple1 checkout1)
    (on_top bottle_of_orange_juice1 checkout1)
    (at checkout1 grocery_store)
    (at sack1 grocery_store)
    (at sack2 grocery_store)
    (at canned_food1 grocery_store)
    (at egg1 grocery_store)
    (at apple1 grocery_store)
    (at bottle_of_orange_juice1 grocery_store)
    (at robot1 grocery_store)
    (robot_free robot1)
  )
  (:goal
  (and
    (in canned_food1 sack1)
    (in egg1 sack1)
    (in apple1 sack1)
    (in bottle_of_orange_juice1 sack1)
  )
)
)
