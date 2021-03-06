import sys
import argparse
from common import read_sentences
import config

def main():
    parser = argparse.ArgumentParser(description='Create source ||| lemma_tag corpus')
    parser.add_argument('--partial', action='store_true',
            help='exclude non-predicted categories from lemmatization')
    args = parser.parse_args()

    def lemmatize(tgt, lemma, tag):
        if args.partial and tag[0] not in config.EXTRACTED_TAGS:
            return tgt
        return lemma+'_'+tag[0]

    for source, target, _ in read_sentences(sys.stdin):
        src = ' '.join(w.token for w in source)
        tgt = ' '.join(lemmatize(tgt, lemma, tag) for tgt, lemma, tag in target)
        print(u'{} ||| {}'.format(src, tgt).encode('utf8'))

if __name__ == '__main__':
    main()

