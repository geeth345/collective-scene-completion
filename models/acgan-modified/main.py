# code source: https://github.com/eriklindernoren/Keras-GAN/blob/master/acgan/acgan.py paper: Cheng, Keyang,
# Rabia Tahir, Lubamba Kasangu Eric, and Maozhen Li, ‘An Analysis of Generative Adversarial Networks and Variants for
# Image Synthesis on MNIST Dataset’, Multimedia Tools and Applications, 79.19 (2020), 13725–52
# <https://doi.org/10.1007/s11042-019-08600-2>

from __future__ import print_function, division

from keras.datasets import mnist
from keras.layers import Input, Dense, Reshape, Flatten, Dropout, multiply
from keras.layers import BatchNormalization, Activation, Embedding, ZeroPadding2D
from keras.layers import LeakyReLU
from keras.layers import UpSampling2D, Conv2D
from keras.models import Sequential, Model
from keras.optimizers.legacy import Adam

import matplotlib.pyplot as plt

import random

import numpy as np

class ACGAN():
    def __init__(self):
        # Input shape
        self.img_rows = 28
        self.img_cols = 28
        self.channels = 1
        self.img_shape = (self.img_rows, self.img_cols, self.channels)
        self.num_classes = 10
        self.latent_dim = 100

        optimizer = Adam(0.0002, 0.5)
        losses = ['binary_crossentropy', 'sparse_categorical_crossentropy']

        # Build and compile the discriminator
        self.discriminator = self.build_discriminator()
        self.discriminator.compile(loss=losses,
            optimizer=optimizer,
            metrics=['accuracy'])

        # Build the generator
        self.generator = self.build_generator()

        # The generator takes a masked image as input
        masked_image = Input(shape=self.img_shape)
        img = self.generator(masked_image)

        # For the combined model we will only train the generator
        self.discriminator.trainable = False

        # The discriminator takes generated image as input and determines validity
        # and the label of that image
        valid, target_label = self.discriminator(img)

        # The combined model  (stacked generator and discriminator)
        # Trains the generator to fool the discriminator
        self.combined = Model(masked_image, [valid, target_label])
        self.combined.compile(loss=losses,
            optimizer=optimizer)

        # load the mnist dataset
        (X_train, y_train), (X_test, y_test) = mnist.load_data()
        self.X_train = X_train
        self.y_train = y_train
        self.X_test = X_test
        self.y_test = y_test

        # create a masked version of the test set
        self.X_test_masked = np.array([mask(img) for img in self.X_test])

        # for evaluation
        self.accuracy_scores = []
        self.recall_scores = []


    def build_generator(self):

        model = Sequential()

        model.add(Conv2D(64, kernel_size=3, strides=1, padding="same", input_shape=self.img_shape))
        model.add(Activation("relu"))
        model.add(BatchNormalization(momentum=0.8))

        # Adding additional Conv2D layers
        model.add(Conv2D(128, kernel_size=3, strides=1, padding="same"))
        model.add(Activation("relu"))
        model.add(BatchNormalization(momentum=0.8))

        model.add(Conv2D(64, kernel_size=3, strides=1, padding="same"))
        model.add(Activation("relu"))
        model.add(BatchNormalization(momentum=0.8))

        # Final Conv2D layer to reconstruct the image
        model.add(Conv2D(self.channels, kernel_size=3, strides=1, padding='same'))
        model.add(Activation("tanh"))


        model.summary()

        # use masked images as inputs to the model
        masked_image = Input(shape=self.img_shape)

        img = model(masked_image)

        return Model(masked_image, img)

    def build_discriminator(self):

        model = Sequential()

        model.add(Conv2D(16, kernel_size=3, strides=2, input_shape=self.img_shape, padding="same"))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(Conv2D(32, kernel_size=3, strides=2, padding="same"))
        model.add(ZeroPadding2D(padding=((0,1),(0,1))))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(64, kernel_size=3, strides=2, padding="same"))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(128, kernel_size=3, strides=1, padding="same"))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))

        model.add(Flatten())
        model.summary()

        img = Input(shape=self.img_shape)

        # Extract feature representation
        features = model(img)

        # Determine validity and label of the image
        validity = Dense(1, activation="sigmoid")(features)
        label = Dense(self.num_classes, activation="softmax")(features)

        return Model(img, [validity, label])

    def train(self, epochs, batch_size=128, sample_interval=50):

        # Load the dataset
        X_train = self.X_train
        y_train = self.y_train

        # Configure inputs
        X_train = (X_train.astype(np.float32) - 127.5) / 127.5
        X_train = np.expand_dims(X_train, axis=3)
        y_train = y_train.reshape(-1, 1)

        # Adversarial ground truths
        valid = np.ones((batch_size, 1))
        fake = np.zeros((batch_size, 1))

        for epoch in range(epochs):

            # ---------------------
            #  Train Discriminator
            # ---------------------

            # Select a random batch of images
            idx = np.random.randint(0, X_train.shape[0], batch_size)
            imgs = X_train[idx]

            # Generating masked images for training the generator
            masked_imgs = np.array([mask(img) for img in imgs])

            # Generate a half batch of new images
            gen_imgs = self.generator.predict(masked_imgs, verbose=0)

            # Image labels. 0-9
            img_labels = y_train[idx]

            # Train the discriminator
            d_loss_real = self.discriminator.train_on_batch(imgs, [valid, img_labels])
            d_loss_fake = self.discriminator.train_on_batch(gen_imgs, [fake, img_labels])
            d_loss = 0.5 * np.add(d_loss_real, d_loss_fake)

            # ---------------------
            #  Train Generator
            # ---------------------


            # Train the generator
            g_loss = self.combined.train_on_batch(masked_imgs, [valid, img_labels])


            # Plot the progress
            print ("%d [D loss: %f, acc.: %.2f%%, op_acc: %.2f%%] [G loss: %f]" % (epoch, d_loss[0], 100*d_loss[3], 100*d_loss[4], g_loss[0]))

            # If at save interval => save generated image samples
            if epoch % sample_interval == 0:
                self.save_model()
                self.sample_images(epoch)
                self.test_masked_accuracy(epoch)

    def test_masked_accuracy(self, epoch):
        # evaluate the combined model on the masked test set, looking at the accuracy of the labels produced by the discriminator
        # get classifications
        classifications = self.discriminator.predict(self.X_test_masked)[1]
        # get the predicted labels
        predicted_labels = np.argmax(classifications, axis=1)

        accuracy = np.sum(predicted_labels == self.y_test) / len(self.y_test)
        self.accuracy_scores.append((accuracy, epoch))



        # save a plot of the accuracy scores
        plt.plot([score[1] for score in self.accuracy_scores], [score[0] for score in self.accuracy_scores])
        plt.xlabel('Epoch')
        plt.ylabel('Accuracy')
        plt.savefig('images/accuracy.png')
        plt.close()


        # use predicted labels to calculate recall for each class
        recalls = []
        for i in range(10):
            # get the indices of the test images with the current label
            indices = np.where(self.y_test == i)[0]
            predicted_labels = np.argmax(classifications[indices], axis=1)
            recall = np.sum(predicted_labels == i) / len(indices)
            recalls.append(recall)

        self.recall_scores.append((recalls, epoch))

        # save a plot of the recall scores, one line for each class
        for i in range(10):
            plt.plot([score[1] for score in self.recall_scores], [score[0][i] for score in self.recall_scores])
        plt.xlabel('Epoch')
        plt.ylabel('Recall')
        plt.savefig('images/recall.png')
        plt.close()






    def sample_images(self, epoch):
        r, c = 10, 10

        # generate masked images from the test set
        masked_imgs = np.array([mask(img) for img in self.X_test[:r*c]])

        gen_imgs = self.generator.predict(masked_imgs)

        # Rescale images 0 - 1
        gen_imgs = 0.5 * gen_imgs + 0.5

        fig, axs = plt.subplots(r, c)
        cnt = 0
        for i in range(r):
            for j in range(c):
                axs[i,j].imshow(gen_imgs[cnt,:,:,0], cmap='gray')
                axs[i,j].axis('off')
                cnt += 1
        fig.savefig("images/%d.png" % epoch)
        plt.close()

    def save_model(self):

        def save(model, model_name):
            model_path = "saved_model/%s.json" % model_name
            weights_path = "saved_model/%s_weights.hdf5" % model_name
            options = {"file_arch": model_path,
                        "file_weight": weights_path}
            json_string = model.to_json()
            open(options['file_arch'], 'w').write(json_string)
            model.save_weights(options['file_weight'])

        save(self.generator, "generator")
        save(self.discriminator, "discriminator")



# from tqdm import tqdm
# import matplotlib.pyplot as plt



# parameters
RANDOM_WALK_LENGTH = 40
VISIBLE_RADIUS = 5

# given a 28*28 numpy array, apply a mask and return the masked image
def mask(image, walk_length=RANDOM_WALK_LENGTH, visible_radius=VISIBLE_RADIUS):

    if len(image.shape) == 3:
        image = image[:,:,0]


    # assume the image is a 28x28 numpy array
    assert image.shape == (28, 28)


    # randomly select a starting position
    agent_position = (random.randint(7, 20), random.randint(7, 20))
    random_walk_steps = [random.randint(0, 3) for _ in range(RANDOM_WALK_LENGTH)]

    # create the mask
    mask = np.zeros((28, 28))
    for i in range(RANDOM_WALK_LENGTH):
        # update the agent position
        if random_walk_steps[i] == 0:
            agent_position = (agent_position[0] - 1, agent_position[1])
        elif random_walk_steps[i] == 1:
            agent_position = (agent_position[0], agent_position[1] + 1)
        elif random_walk_steps[i] == 2:
            agent_position = (agent_position[0] + 1, agent_position[1])
        elif random_walk_steps[i] == 3:
            agent_position = (agent_position[0], agent_position[1] - 1)

        # update the mask
        for x in range(agent_position[0] - VISIBLE_RADIUS, agent_position[0] + VISIBLE_RADIUS + 1):
            for y in range(agent_position[1] - VISIBLE_RADIUS, agent_position[1] + VISIBLE_RADIUS + 1):
                if 0 <= x < 28 and 0 <= y < 28:
                    mask[x][y] = 1

    # apply the mask
    masked_image = np.multiply(image, mask)
    #
    # # display all three arrays for debugging
    # fig, (ax1, ax2, ax3) = plt.subplots(1, 3)
    # ax1.imshow(image, cmap='gray')
    # ax2.imshow(mask, cmap='gray')
    # ax3.imshow(masked_image, cmap='gray')
    # plt.show()

    return masked_image



if __name__ == '__main__':
    acgan = ACGAN()
    acgan.train(epochs=14000, batch_size=32, sample_interval=200)