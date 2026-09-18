(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        container - item
        residue - item
        device - item
        furniture - locatable
        bath_towel - item
        dirt - residue
        washer - device
        clothes_dryer - device
        detergent_bottle - container
        floor - furniture
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (in ?o - item ?c - container)
        (on_top ?top - item ?bottom - locatable)
        (next_to ?a - item ?b - locatable)
        (under ?a - item ?b - locatable)
        (touching ?a - item ?b - locatable)
        (attached ?a - item ?b - locatable)
        (draped ?a - item ?b - locatable)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
        (covered ?o - locatable ?s - item)
        (open ?t - container)
        (folded ?o - item)
        (unfolded ?o - item)
        (toggled_on ?o - device)
        (hot ?o - locatable)
        (broken ?o - item)
        (on_fire ?o - item)
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

(:action move
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
            (not (robot_free ?r))
            (not (at ?o ?l))
        )
)

(:action place
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?o)
        )
    :effect
        (and
            (at ?o ?l)
            (robot_free ?r)
            (not (holding ?r ?o))
        )
)

(:action place_in_container
    :parameters (?r - robot ?o - item ?c - container ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?c ?l)
            (holding ?r ?o)
            (open ?c)
        )
    :effect
        (and
            (in ?o ?c)
            (robot_free ?r)
            (not (holding ?r ?o))
        )
)

(:action stack
    :parameters (?r - robot ?top - item ?bottom - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?top)
            (at ?bottom ?l)
        )
    :effect
        (and
            (on_top ?top ?bottom)
            (at ?top ?l)
            (robot_free ?r)
            (not (holding ?r ?top))
        )
)

(:action unstack
    :parameters (?r - robot ?top - item ?bottom - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?top ?l)
            (at ?bottom ?l)
            (on_top ?top ?bottom)
            (robot_free ?r)
        )
    :effect
        (and
            (holding ?r ?top)
            (not (robot_free ?r))
            (not (on_top ?top ?bottom))
            (not (at ?top ?l))
        )
)

(:action open
    :parameters (?r - robot ?c - container ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?c ?l)
            (not (open ?c))
        )
    :effect
        (and
            (open ?c)
        )
)

(:action close
    :parameters (?r - robot ?c - container ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?c ?l)
            (open ?c)
        )
    :effect
        (and
            (not (open ?c))
        )
)

(:action push
    :parameters (?r - robot ?o - item ?from - location ?to - location)
    :precondition
        (and
            (at ?r ?from)
            (at ?o ?from)
        )
    :effect
        (and
            (not (at ?r ?from))
            (at ?r ?to)
            (not (at ?o ?from))
            (at ?o ?to)
        )
)

(:action pull
    :parameters (?r - robot ?o - item ?from - location ?to - location)
    :precondition
        (and
            (at ?r ?from)
            (at ?o ?from)
        )
    :effect
        (and
            (not (at ?r ?from))
            (at ?r ?to)
            (not (at ?o ?from))
            (at ?o ?to)
        )
)

(:action pour
    :parameters (?r - robot ?b - detergent_bottle ?target - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?b ?l)
            (holding ?r ?b)
            (at ?target ?l)
            (open ?b)
        )
    :effect
        (and
            (touching ?b ?target)
        )
)

(:action clean
    :parameters (?r - robot ?res - residue ?surf - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?res ?l)
            (at ?surf ?l)
            (covered ?surf ?res)
            (robot_free ?r)
        )
    :effect
        (and
            (not (covered ?surf ?res))
        )
)

(:action fold
    :parameters (?r - robot ?t - bath_towel ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?t ?l)
            (unfolded ?t)
            (robot_free ?r)
        )
    :effect
        (and
            (folded ?t)
            (not (unfolded ?t))
        )
)

(:action unfold
    :parameters (?r - robot ?t - bath_towel ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?t ?l)
            (folded ?t)
            (robot_free ?r)
        )
    :effect
        (and
            (unfolded ?t)
            (not (folded ?t))
        )
)
)
