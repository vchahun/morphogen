import sys
import argparse
import logging
import cPickle
import numpy, math
from collections import defaultdict
import config
import tagset
from common import read_sentences

def extract_instances(source, target, alignment):
    """Extract (category, features, tag) training instances for a sentence pair"""
    for i, (token, lemma, tag) in enumerate(target):
        if tag[0] not in config.EXTRACTED_TAGS: continue
        word_alignments = [j for (k, j) in alignment if k == i] # tgt == i - src
        if len(word_alignments) != 1: continue # Extract only one-to-one alignments
        (j,) = word_alignments # src
        features = dict((fname, fval) for ff in config.FEATURES
                for fname, fval in ff(source, lemma, j))
        yield (token, lemma, tag), features

class SimpleModel:
    def __init__(self, vectorizer, clf):
        self.vectorizer = vectorizer
        self.clf = clf

    def score_all(self, inflections, features):
        fvector = self.vectorizer.transform(features)
        predictions = dict(zip(self.clf.classes_, self.clf.predict_log_proba(fvector)[0]))
        scored = [(predictions.get(tag, float('-inf')), tag, inflection)
                for tag, inflection in inflections]
        z = numpy.logaddexp.reduce([score for score, _, _ in scored])
        return [(score - z, tag, inflection) for score, tag, inflection in scored]

class VectorModel:
    def __init__(self, category, vectorizer, clfs):
        self.category = tagset.categories[category]
        self.vectorizer = vectorizer
        self.clfs = clfs

    def score_all(self, inflections, features):
        fvector = self.vectorizer.transform([features])
        score_vectors = {}
        for i, clf in self.clfs.iteritems():
            if clf is None: # univalued attribute
                score_vectors[i] = defaultdict(int)
            else:
                score_vectors[i] = dict(zip(clf.classes_, clf.predict_log_proba(fvector)[0]))
        score = lambda tag: sum(score_vectors[i][v]
                for i, v in enumerate(tag.ljust(tagset.tag_length[self.category], '-')))
        scored = [(score(tag), tag, inflection) for tag, inflection in inflections]
        z = numpy.logaddexp.reduce([score for score, _, _ in scored])
        return [(score - z, tag, inflection) for score, tag, inflection in scored]
        

def make_model(category, v, m):
    if isinstance(m, dict):
        return VectorModel(category, v, m)
    return SimpleModel(v, m)

def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    parser = argparse.ArgumentParser(description='Predict using trained models')
    parser.add_argument('rev_map', help='reverse inflection map')
    parser.add_argument('models', nargs='+', help='trained models')
    args = parser.parse_args()

    logging.info('Loading reverse inflection map')
    with open(args.rev_map) as f:
        rev_map = cPickle.load(f)

    models = {}
    logging.info('Loading inflection prediction models')
    for fn in args.models:
        with open(fn) as f:
            category, v, m = cPickle.load(f)
            models[category] = make_model(category, v, m)

    logging.info('Loaded models for %d categories', len(models))

    stats = {cat: [0, 0, 0, 0] for cat in config.EXTRACTED_TAGS}

    for source, target, alignment in read_sentences(sys.stdin):
        for word, features in extract_instances(source, target, alignment):
            gold_inflection, lemma, tag = word
            category = tag[0]
            gold_tag = tag[1:]
            possible_inflections = rev_map.get((lemma, category), [])
            if (gold_tag, gold_inflection) not in possible_inflections:
                print(u'Expected: {} ({}) not found'.format(gold_inflection,
                    gold_tag).encode('utf8'))
                continue

            model = models[category]

            scored_inflections = model.score_all(possible_inflections, features)
            ranked_inflections = sorted(scored_inflections, reverse=True)
            predicted_score, predicted_tag, predicted_inflection = ranked_inflections[0]

            gold_rank = 1 + [tag for _, tag, _ in ranked_inflections].index(gold_tag)
            gold_score = next((score for score, tag, _ in ranked_inflections if tag == gold_tag))

            print(u'Expected: {} ({}) r={} score={:.3f} |'
                    ' Predicted: {} ({}) score={:.3f}'.format(gold_inflection,
                gold_tag, gold_rank, gold_score, predicted_inflection, predicted_tag,
                predicted_score).encode('utf8'))
            
            stats[category][0] += 1
            stats[category][1] += 1/float(gold_rank)
            stats[category][2] += (gold_inflection == predicted_inflection)
            stats[category][3] += gold_score

    for category, (n_instances, rrank_sum, n_correct, total_log_prob) in stats.items():
        if n_instances == 0: continue
        mrr = rrank_sum/n_instances
        accuracy = n_correct/float(n_instances)
        ppl = math.exp(-total_log_prob/n_instances)
        print('Category {}: MRR={:.3f} acc={:.3f} ppl={:.1f} ({:>4} instances)'.format(category, mrr, accuracy, ppl, n_instances))

if __name__ == '__main__':
    main()
