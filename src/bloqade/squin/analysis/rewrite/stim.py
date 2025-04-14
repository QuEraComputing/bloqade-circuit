from typing import Dict
from dataclasses import dataclass

from bloqade.analysis.address import Address
from bloqade.squin.analysis.nsites import Sites

from kirin import ir
from kirin.rewrite.abc import RewriteResult, RewriteRule


@dataclass
class SquinToStim(RewriteRule):
    
    # Somehow need to plug in Address and Sites
    # into the SSAValue Hints field, which only accepts
    # Attribute types

    ## Could literally just plug in `ir.Attribute` into
    ## the Address and Site lattices? 
    ## Couldn't I just create my own attributes instead?

    address_analysis: Dict[ir.SSAValue, Address]
    op_site_analysis: Dict[ir.SSAValue, Sites] 

    # need to plug in data into the SSAValue 
    # for the rewrite from these passes,
    # then something should look at those hints 
    # and generate the corresponding stim statements 

    pass