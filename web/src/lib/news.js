/* What leads the page: an item the pipeline's model judged to be news (its `signal`), or, until an item has been judged, one from a
   vendor's own changelog feed. No wording is matched here. */
export const announced = i => (i.signal ? i.signal !== 'other' : i.kind === 'changelog');
