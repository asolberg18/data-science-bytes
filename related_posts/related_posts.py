"""
Related posts plugin for Pelican
================================

Adds related_posts variable to article's context
"""

import os
from collections import defaultdict

from bs4 import BeautifulSoup
from nltk.tokenize import RegexpTokenizer
import nltk
from pelican import signals
from gensim import corpora, models, similarities


def filter_dictionary(raw_dictionary,
                      stop_words=nltk.corpus.stopwords.words('english'),
                      min_count=2):
    """Filter raw_dictionary inplace to remove stopwords and words occurring
    less than min_count number of times.

    Will compactify the dictionary before exiting.

    :param raw_dictionary: gensim.corpora.Dictionary to filter
    :param stop_words: iterable of words to remove
    :param min_count: int minimum word count in resulting dictionary
    """
    stop_ids = [raw_dictionary.token2id[word] for word in stop_words
                if word in raw_dictionary.token2id]
    rare_ids = [id for id, freq in raw_dictionary.dfs.iteritems()
                if freq < min_count]
    raw_dictionary.filter_tokens(stop_ids + rare_ids)
    raw_dictionary.compactify()


def generate_similarity_index(documents, model=models.LsiModel):
    """Return gensim.MatrixSimilarity of text documents using the supplied
    model.

    :param documents: An iterable of documents consisting of a list of words
    :param model: gensim.models to apply
    :return: gensim.MatrixSimilary the similarity values for every document to
        every other document.
    """
    dictionary = corpora.Dictionary(documents)
    filter_dictionary(dictionary)
    corpus = [dictionary.doc2bow(doc) for doc in documents]
    topic_model = model(corpus, id2word=dictionary, num_topics=5)
    for topic in topic_model.print_topics():
        print topic
    return similarities.MatrixSimilarity(topic_model[corpus])


def recommend_articles(articles, tokenizer=RegexpTokenizer(r'\w+')):
    """Return a dictionary keyed by article source_path whose values are a
    sorted (descending) list of (article.source_path, similarity_score) tuples
    for every other article.

    HTML tags are stripped.

    :param articles: articles from a pelican ArticleGenerator
    :param tokenizer: an nltk tokenizer used to split article text into words
    :return: dictionary of similarity scores of other articles to keyed article
    """
    article_texts = [BeautifulSoup(article.content).get_text().lower()
                     for article in articles]
    documents = [tokenizer.tokenize(text) for text in article_texts]
    index = generate_similarity_index(documents)
    similarity_scores = defaultdict(list)
    for article, sims in zip(articles, index):
        sims = sorted(enumerate(sims), key=lambda item: -item[1])
        for id, score in sims:
            if article == articles[id]:
                continue
            similarity_scores[os.path.abspath(article.source_path)].append(
                (articles[id].source_path, score)
            )
    return similarity_scores


def add_related_posts(generator, default_max_related_posts=5):
    """Find articles related to each article in a pelican ArticleGenerator and
    add the source_paths of the related articles and their similarity scores to
    the article metadata.

    :param generator: a pelican ArticleGenerator
    :param default_max_related_posts: the default max number of most similar
     posts. This will be overridden if MAX_RELATED_POSTS is set in the pelican
     config file.
    """

    max_posts = generator.settings.get("MAX_RELATED_POSTS",
                                       default_max_related_posts)
    similarity_scores = recommend_articles(generator.articles)
    articles_by_path = {art.source_path: art for art in generator.articles}
    for article in generator.articles:
        related_posts = sorted(similarity_scores[article.source_path],
                               key=lambda x: -x[1])
        article.related_posts = []
        article.score = {}
        for i, entry in enumerate(related_posts):
            if i >= max_posts:
                break
            source_path, similarity = entry
            try:
                related_post = articles_by_path[source_path]
                article.score[unicode(related_post.source_path)] = similarity
            except KeyError:
                print "can't find article {}".format(source_path)
            article.related_posts.append(related_post)


def register():
    """Entry point for ArticleGenerator from pelican"""
    signals.article_generator_finalized.connect(add_related_posts)
