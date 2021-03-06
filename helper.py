import re
import random
import numpy as np
import os.path
import scipy.misc
import shutil
import zipfile
import time
import tensorflow as tf
from glob import glob
from urllib.request import urlretrieve
from tqdm import tqdm
from imgaug import augmenters as iaa
from sklearn.model_selection import train_test_split



class DLProgress(tqdm):
    last_block = 0

    def hook(self, block_num=1, block_size=1, total_size=None):
        self.total = total_size
        self.update((block_num - self.last_block) * block_size)
        self.last_block = block_num


def maybe_download_pretrained_vgg(data_dir):
    """
    Download and extract pretrained vgg model if it doesn't exist
    :param data_dir: Directory to download the model to
    """
    vgg_filename = 'vgg.zip'
    vgg_path = os.path.join(data_dir, 'vgg')
    vgg_files = [
        os.path.join(vgg_path, 'variables/variables.data-00000-of-00001'),
        os.path.join(vgg_path, 'variables/variables.index'),
        os.path.join(vgg_path, 'saved_model.pb')]

    missing_vgg_files = [vgg_file for vgg_file in vgg_files if not os.path.exists(vgg_file)]
    if missing_vgg_files:
        # Clean vgg dir
        if os.path.exists(vgg_path):
            shutil.rmtree(vgg_path)
        os.makedirs(vgg_path)

        # Download vgg
        print('Downloading pre-trained vgg model...')
        with DLProgress(unit='B', unit_scale=True, miniters=1) as pbar:
            urlretrieve(
                'https://s3-us-west-1.amazonaws.com/udacity-selfdrivingcar/vgg.zip',
                os.path.join(vgg_path, vgg_filename),
                pbar.hook)

        # Extract vgg
        print('Extracting model...')
        zip_ref = zipfile.ZipFile(os.path.join(vgg_path, vgg_filename), 'r')
        zip_ref.extractall(data_dir)
        zip_ref.close()

        # Remove zip file to save space
        os.remove(os.path.join(vgg_path, vgg_filename))


def preprocess_labels(label_image):
    labels_new = np.zeros_like(label_image)
    lane_marking_pixels = (label_image[:,:,0] == 6).nonzero()
    labels_new[lane_marking_pixels] = 1
    lane_marking_pixels = (label_image[:,:,0] == 7).nonzero()
    labels_new[lane_marking_pixels] = 1
    lane_marking_pixels = (label_image[:,:,0] == 10).nonzero()
    labels_new[lane_marking_pixels] = 2

    vehicle_pixels = (label_image[:,:,0] == 10).nonzero()
    # Isolate vehicle pixels associated with the hood (y-position > 496)
    hood_indices = (vehicle_pixels[0] >= 496).nonzero()[0]
    hood_pixels = (vehicle_pixels[0][hood_indices],
                   vehicle_pixels[1][hood_indices])
    # Set hood pixel labels to 0
    labels_new[hood_pixels] = 0
    # Identify lane marking pixels (label is 6)
    return labels_new

def process_carla(BASE_DIR='Train'):
    image_paths = sorted(glob(os.path.join(BASE_DIR, 'CameraSeg', '*.png')))
    label_paths = sorted(glob(os.path.join(BASE_DIR, 'CameraRGB', '*.png')))
    for image, label in zip(image_paths, label_paths):
        X_train, X_test, y_train, y_test = train_test_split(image_paths,
                            label_paths, test_size=0.33, random_state=42)
    if not os.path.exists(os.path.join("training", "CameraRGB")):
        os.makedirs(os.path.join("training", "CameraRGB"))
        os.makedirs(os.path.join("training", "CameraSeg"))
        os.makedirs(os.path.join("valid", "CameraRGB"))
        os.makedirs(os.path.join("valid", "CameraSeg"))
    for x,y in zip(X_train,y_train):
        os.rename(os.path.join(BASE_DIR, "CameraRGB",os.path.basename(x)),
                 os.path.join("training", "CameraRGB", os.path.basename(x)))
        os.rename(os.path.join(BASE_DIR,"CameraSeg" ,os.path.basename(y)),
                 os.path.join("training", "CameraSeg", os.path.basename(y)))
    for x,y in zip(X_test,y_test):
        os.rename(os.path.join(BASE_DIR, "CameraRGB",os.path.basename(x)),
                 os.path.join("valid", "CameraRGB", os.path.basename(x)))
        os.rename(os.path.join(BASE_DIR,"CameraSeg" ,os.path.basename(y)),
                 os.path.join("valid", "CameraSeg", os.path.basename(y)))

def split_data(BASE_DIR='data_road'):
    data_folder = os.path.join(BASE_DIR,'full_training')
    os.makedirs(data_folder)
    os.rename(os.path.join(BASE_DIR, 'training'), data_folder)
    image_paths = glob(os.path.join(data_folder, 'image_2', '*.png'))
    label_paths = [path for path in glob(os.path.join(data_folder, 'gt_image_2', '*_road_*.png'))]
    X_train, X_test, y_train, y_test = train_test_split(sorted(image_paths),
                        sorted(label_paths), test_size=0.33, random_state=42)
    if not os.path.exists(os.path.join(BASE_DIR,"training", "image_2")):
        os.makedirs(os.path.join(BASE_DIR,"training", "image_2"))
        os.makedirs(os.path.join(BASE_DIR,"training", "gt_image_2"))
        os.makedirs(os.path.join(BASE_DIR,"valid", "image_2"))
        os.makedirs(os.path.join(BASE_DIR,"valid", "gt_image_2"))
    for x,y in zip(X_train,y_train):
        os.rename(os.path.join(BASE_DIR,'full_training', 'image_2',os.path.basename(x)),
                 os.path.join(BASE_DIR,"training", "image_2", os.path.basename(x)))
        os.rename(os.path.join(BASE_DIR,'full_training', 'gt_image_2',os.path.basename(y)),
                 os.path.join(BASE_DIR,"training", "gt_image_2", os.path.basename(y)))
    for x,y in zip(X_test,y_test):
        os.rename(os.path.join(BASE_DIR,'full_training', 'image_2',os.path.basename(x)),
                 os.path.join(BASE_DIR,"valid", "image_2", os.path.basename(x)))
        os.rename(os.path.join(BASE_DIR,'full_training', 'gt_image_2',os.path.basename(y)),
             os.path.join(BASE_DIR,"valid", "gt_image_2", os.path.basename(y)))

def gen_batch_carla_function(data_folder, image_shape, train=True):
    """
    Generate function to create batches of training data
    :param data_folder: Path to folder that contains all the datasets
    :param image_shape: Tuple - Shape of image
    :return:
    """
    _train = train
    seq = iaa.Sequential([
        iaa.Fliplr(0.5), # horizontal flips
        iaa.Crop(percent=(0, 0.1)), # random crops
        # Small gaussian blur with random sigma between 0 and 0.5.
        # But we only blur about 50% of all images.
        # iaa.Sometimes(0.5,
        #     iaa.GaussianBlur(sigma=(0, 0.5))
        # ),
        # Strengthen or weaken the contrast in each image.
        iaa.ContrastNormalization((0.75, 1.5)),
        # Add gaussian noise.
        # For 50% of all images, we sample the noise once per pixel.
        # For the other 50% of all images, we sample the noise per pixel AND
        # channel. This can change the color (not only brightness) of the
        # pixels.
        # iaa.AdditiveGaussianNoise(loc=0, scale=(0.0, 0.05*255), per_channel=0.5),
        # Make some images brighter and some darker.
        # In 20% of all cases, we sample the multiplier once per channel,
        # which can end up changing the color of the images.
        # iaa.Multiply((0.8, 1.2), per_channel=0.2),
        # Apply affine transformations to each image.
        # Scale/zoom them, translate/move them, rotate them and shear them.
        iaa.Affine(
            scale={"x": (0.8, 1.2), "y": (0.8, 1.2)},
            translate_percent={"x": (-0.2, 0.2), "y": (-0.2, 0.2)},
            rotate=(-15, 15)
           # shear=(-8, 8)
        )
    ], random_order=True) # apply augmenters in random order

    def get_batches_fn(batch_size):
        """
        Create batches of training data
        :param batch_size: Batch Size
        :return: Batches of training data
        """
        image_paths = glob(os.path.join(data_folder, 'CameraRGB', '*.png'))
        label_paths = {os.path.basename(path): path for path in glob(os.path.join(data_folder, 'gt_image_2', '*_road_*.png'))}
        background_color = np.array([255, 0, 0])

        random.shuffle(image_paths)
        for batch_i in range(0, len(image_paths), batch_size):
            images = []
            gt_images = []
            for image_file in image_paths[batch_i:batch_i+batch_size]:
                gt_image_file = label_paths[os.path.basename(image_file)]
                image = scipy.misc.imresize(scipy.misc.imread(image_file), image_shape)
                gt_image = scipy.misc.imresize(scipy.misc.imread(gt_image_file), image_shape)
                if _train:
                    seq_det = seq.to_deterministic()
                    image = seq_det.augment_image(image)
                    gt_image = seq_det.augment_image(gt_image)
                gt_bg = np.all(gt_image == background_color, axis=2)
                gt_bg = gt_bg.reshape(*gt_bg.shape, 1)
                gt_image = np.concatenate((gt_bg, np.invert(gt_bg)), axis=2)
                images.append(image)
                gt_images.append(gt_image)
            yield np.array(images), np.array(gt_images)
    return get_batches_fn

def gen_batch_function(data_folder, image_shape, train=True):
    """
    Generate function to create batches of training data
    :param data_folder: Path to folder that contains all the datasets
    :param image_shape: Tuple - Shape of image
    :return:
    """
    _train = train
    seq = iaa.Sequential([
        iaa.Fliplr(0.5), # horizontal flips
        iaa.Crop(percent=(0, 0.1)), # random crops
        # Small gaussian blur with random sigma between 0 and 0.5.
        # But we only blur about 50% of all images.
        # iaa.Sometimes(0.5,
        #     iaa.GaussianBlur(sigma=(0, 0.5))
        # ),
        # Strengthen or weaken the contrast in each image.
        iaa.ContrastNormalization((0.75, 1.5)),
        # Add gaussian noise.
        # For 50% of all images, we sample the noise once per pixel.
        # For the other 50% of all images, we sample the noise per pixel AND
        # channel. This can change the color (not only brightness) of the
        # pixels.
        # iaa.AdditiveGaussianNoise(loc=0, scale=(0.0, 0.05*255), per_channel=0.5),
        # Make some images brighter and some darker.
        # In 20% of all cases, we sample the multiplier once per channel,
        # which can end up changing the color of the images.
        # iaa.Multiply((0.8, 1.2), per_channel=0.2),
        # Apply affine transformations to each image.
        # Scale/zoom them, translate/move them, rotate them and shear them.
        iaa.Affine(
            scale={"x": (0.8, 1.2), "y": (0.8, 1.2)},
            translate_percent={"x": (-0.2, 0.2), "y": (-0.2, 0.2)},
            rotate=(-15, 15)
           # shear=(-8, 8)
        )
    ], random_order=True) # apply augmenters in random order

    def get_batches_fn(batch_size):
        """
        Create batches of training data
        :param batch_size: Batch Size
        :return: Batches of training data
        """
        image_paths = glob(os.path.join(data_folder, 'image_2', '*.png'))
        label_paths = {
            re.sub(r'_(lane|road)_', '_', os.path.basename(path)): path
            for path in glob(os.path.join(data_folder, 'gt_image_2', '*_road_*.png'))}
        background_color = np.array([255, 0, 0])

        random.shuffle(image_paths)
        for batch_i in range(0, len(image_paths), batch_size):
            images = []
            gt_images = []
            for image_file in image_paths[batch_i:batch_i+batch_size]:
                gt_image_file = label_paths[os.path.basename(image_file)]
                image = scipy.misc.imresize(scipy.misc.imread(image_file), image_shape)
                gt_image = scipy.misc.imresize(scipy.misc.imread(gt_image_file), image_shape)
                if _train:
                    seq_det = seq.to_deterministic()
                    image = seq_det.augment_image(image)
                    gt_image = seq_det.augment_image(gt_image)
                gt_bg = np.all(gt_image == background_color, axis=2)
                gt_bg = gt_bg.reshape(*gt_bg.shape, 1)
                gt_image = np.concatenate((gt_bg, np.invert(gt_bg)), axis=2)
                images.append(image)
                gt_images.append(gt_image)
            yield np.array(images), np.array(gt_images)
    return get_batches_fn

def gen_test_output(sess, logits, keep_prob, image_pl, data_folder, image_shape):
    """
    Generate test output using the test images
    :param sess: TF session
    :param logits: TF Tensor for the logits
    :param keep_prob: TF Placeholder for the dropout keep robability
    :param image_pl: TF Placeholder for the image placeholder
    :param data_folder: Path to the folder that contains the datasets
    :param image_shape: Tuple - Shape of image
    :return: Output for for each test image
    """
    for image_file in glob(os.path.join(data_folder, 'image_2', '*.png')):
        image = scipy.misc.imresize(scipy.misc.imread(image_file), image_shape)

        im_softmax = sess.run(
            [tf.nn.softmax(logits)],
            {keep_prob: 1.0, image_pl: [image]})
        im_softmax = im_softmax[0][:, 1].reshape(image_shape[0], image_shape[1])
        segmentation = (im_softmax > 0.5).reshape(image_shape[0], image_shape[1], 1)
        mask = np.dot(segmentation, np.array([[0, 255, 0, 127]]))
        mask = scipy.misc.toimage(mask, mode="RGBA")
        street_im = scipy.misc.toimage(image)
        street_im.paste(mask, box=None, mask=mask)

        yield os.path.basename(image_file), np.array(street_im)


def save_inference_samples(runs_dir, data_dir, sess, image_shape, logits, keep_prob, input_image):
    # Make folder for current run
    output_dir = os.path.join(runs_dir, str(time.time()))
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    # Run NN on test images and save them to HD
    print('Training Finished. Saving test images to: {}'.format(output_dir))
    image_outputs = gen_test_output(
        sess, logits, keep_prob, input_image, os.path.join(data_dir, 'data_road/testing'), image_shape)
    for name, image in image_outputs:
        scipy.misc.imsave(os.path.join(output_dir, name), image)
