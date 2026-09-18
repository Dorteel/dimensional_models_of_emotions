(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        furniture - locatable
        garment - item
        tablecloth - garment
        sock - garment
        trouser - garment
        dishtowel - garment
        bed - furniture
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (on_top ?top - item ?bottom - locatable)
        (folded ?o - garment)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
    )

    ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;; ACTION ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

    (:action drive
    :parameters (?r - robot ?from - location ?to - location)
    :precondition
        (and
            (at ?r ?from)
        )
    :effect
        (and
            (not (at ?r ?from))
            (at ?r ?to)
        )
)

(:action pick
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
            (robot_free ?r)
        )
    :effect
        (and
            (holding ?r ?o)
            (not (at ?o ?l))
            (not (robot_free ?r))
        )
)

(:action fold
    :parameters (?r - robot ?g - garment ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?g ?l)
            (robot_free ?r)
        )
    :effect
        (and
            (folded ?g)
        )
)
)
